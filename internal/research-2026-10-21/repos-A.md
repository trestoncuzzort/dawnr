# Repository scout A: D1, D2, D3, D7 (250 repositories)

- Date (UTC): 2026-10-21
- Method: 462 gh search repos calls (378 distinct query strings): 50 plain-match queries, 286 readme-match or topic queries, 48 name-only checks for named projects, 69 name-only discovery queries, and 9 check calls; 35 gh repo view confirmations of repositories named in 23 WebSearch queries (standard mode), 33 resolved; pool of 22,191 distinct repositories (deduplicated on full name, case-insensitive) from 28,453 raw hits; filtered with keyword groups (formal-verification terms with LLM or specification terms; RL and verifier-reward terms; serving, grammar, speculative and quantization terms), then star thresholds and hand review; dawnr excluded; star counts and dates as reported by gh on 2026-10-21; last update is GitHub updatedAt; licence is the gh licence key mapped to its SPDX id ("other" recorded as NOASSERTION, a missing key as unknown).
- Issues: D1 specification synthesis tools (pre- and postconditions, invariants, autoformalization, spec quality); D2 repair loops and agents (verifier feedback, counterexamples, proof agents, Lean and Coq tooling); D3 RL with verifier rewards and low-VRAM training; D7 small-model serving, constrained and speculative decoding, quantization, GGUF tools.
- Totals: 250 entries; D1 45, D2 82, D3 83, D7 70 (an entry can carry more than one tag); permissive licences (MIT, MIT-0, Apache-2.0, BSD, ISC, MPL-2.0, 0BSD) on 184 entries; star median 213.0.

| # | repo | link | stars | last update | language | licence | issues | why it may help |
|---|---|---|---|---|---|---|---|---|
| 1 | microsoft/verus-proof-synthesis | https://github.com/microsoft/verus-proof-synthesis | 123 | 2026-10-20 | Rust | MIT | D1, D2 | LLM proof and spec drafting for Verus with verifier-error repair, plus the Verus-Bench and VeruSAGE-Bench suites. |
| 2 | ChuyueSun/Clover | https://github.com/ChuyueSun/Clover | 50 | 2026-09-26 | Dafny | MIT | D1, D2 | Closed-loop check that generated code, docstrings and Dafny annotations agree, a consistency signal for the specification stage. |
| 3 | namin/llm-verified-with-monte-carlo-tree-search | https://github.com/namin/llm-verified-with-monte-carlo-tree-search | 295 | 2026-09-26 | Jupyter Notebook | MIT | D1, D2 | LLM-generated verified programs explored with Monte Carlo tree search, a search loop around a verifier. |
| 4 | cmu-l3/alphaverus | https://github.com/cmu-l3/alphaverus | 34 | 2026-09-17 | Python | unknown | D1, D2 | Translation and tree-refinement pipeline that bootstraps Verus proofs using verifier feedback. |
| 5 | dafny-lang/dafny | https://github.com/dafny-lang/dafny | 3587 | 2026-10-19 | C# | NOASSERTION | D1, D2 | Dafny verification-aware language; its specification syntax and verifier messages are the targets for spec synthesis and repair. |
| 6 | sun-wendy/DafnyBench | https://github.com/sun-wendy/DafnyBench | 69 | 2026-10-13 | Dafny | Apache-2.0 | D1 | Dafny benchmark for LLM-written proof hints and annotations, a yardstick for the specification stage. |
| 7 | Beneficial-AI-Foundation/vericoding-benchmark | https://github.com/Beneficial-AI-Foundation/vericoding-benchmark | 52 | 2026-10-12 | Lean | MIT | D1 | Vericoding benchmark of formal specifications paired with verified code in Dafny, Verus and Lean. |
| 8 | JGalego/awesome-vericoding | https://github.com/JGalego/awesome-vericoding | 3 | 2026-10-18 | Python | CC0-1.0 | D1 | Curated list of formally verified code resources, including AI-written specifications and proofs. |
| 9 | m-zest/TrojanSpec-Bench-v1.0 | https://github.com/m-zest/TrojanSpec-Bench-v1.0 | 0 | 2026-05-24 | Python | NOASSERTION | D1 | Benchmark for adversarial specification elicitation, a test of whether generated specifications can be gamed. |
| 10 | metareflection/dafny-annotator | https://github.com/metareflection/dafny-annotator | 21 | 2026-10-15 | Python | MIT | D1 | AI-assisted verification of Dafny programs, a direct reference for adding annotations to Dafny code. |
| 11 | AdaCore/spark2014 | https://github.com/AdaCore/spark2014 | 330 | 2026-10-20 | Ada | GPL-3.0 | D1 | SPARK contracts and proof toolchain for Ada, the contract-first counterpart to Dafny; GPL-3.0, reference only. |
| 12 | evdenis/acsl-skills | https://github.com/evdenis/acsl-skills | 3 | 2026-10-04 | Shell | MIT | D1 | Agent skills for writing ACSL specifications and triaging Frama-C WP runs, a specification-stage playbook. |
| 13 | sysprog21/frama-c-mcp | https://github.com/sysprog21/frama-c-mcp | 35 | 2026-10-16 | Rust | MIT | D1, D2 | MCP server giving agents Frama-C EVA and WP plus sandboxed ACSL iteration. |
| 14 | microsoft/loop-invariant-gen-experiments | https://github.com/microsoft/loop-invariant-gen-experiments | 35 | 2026-07-20 | Python | MIT | D1 | LLM loop invariant generation experiments, a reference for invariant candidates and their checks. |
| 15 | microsoft/NeuralInvariantRanker | https://github.com/microsoft/NeuralInvariantRanker | 13 | 2026-07-05 | Slash | MIT | D1 | Ranks LLM-generated loop invariants for program verification, a candidate filter for the specification stage. |
| 16 | dynaroars/dig | https://github.com/dynaroars/dig | 58 | 2026-10-20 | Python | MIT | D1 | Numerical invariant generator, a non-LLM source of candidate invariants and a baseline for the specification stage. |
| 17 | Lezhi-Ma/SpecGen-Artifact | https://github.com/Lezhi-Ma/SpecGen-Artifact | 22 | 2026-08-13 | Java | MIT | D1 | Artifact for an LLM technique that generates JML specifications and keeps those a verifier accepts. |
| 18 | specgen/specgen | https://github.com/specgen/specgen | 28 | 2026-06-08 | HTML | unknown | D1 | Extended SpecGen project for generating formal program specifications with LLMs. |
| 19 | deskchen/autospec | https://github.com/deskchen/autospec | 10 | 2026-10-07 | C | unknown | D1 | Program specification synthesis with LLMs using static analysis and prompting, a specification-stage reference. |
| 20 | YxCai-SZU/TSFT | https://github.com/YxCai-SZU/TSFT | 3 | 2026-09-17 | C | unknown | D1, D3 | Two-stage fine-tuning for ACSL specification generation, a training recipe for the specification stage. |
| 21 | Mondego/vRAG | https://github.com/Mondego/vRAG | 56 | 2026-10-13 | Dafny | GPL-3.0 | D1, D2 | Verified code synthesis with retrieval-augmented generation, linking generation to verifier checks. |
| 22 | Mondego/vACT | https://github.com/Mondego/vACT | 5 | 2026-07-01 | Java | GPL-3.0 | D1 | Verifiable specification synthesis with feedback from a specification harness. |
| 23 | JasonGross/autoformalization-transpilation | https://github.com/JasonGross/autoformalization-transpilation | 21 | 2026-09-24 | Rocq Prover | MIT | D1 | LLM-based transpilation from Coq to Lean, relevant to moving specifications between proof kernels. |
| 24 | Purewhite2019/rethinking_autoformalization | https://github.com/Purewhite2019/rethinking_autoformalization | 30 | 2026-09-13 | Python | Apache-2.0 | D1 | Faithful autoformalization metric and dependency retrieval for natural-language-to-Lean statements. |
| 25 | loganrjmurphy/LeanEuclid | https://github.com/loganrjmurphy/LeanEuclid | 144 | 2026-10-13 | Lean | MIT | D1 | Autoformalization benchmark in Euclidean geometry targeting Lean, a faithfulness yardstick. |
| 26 | scottnarmstrong/LeanAutoformalizationSkills | https://github.com/scottnarmstrong/LeanAutoformalizationSkills | 51 | 2026-10-20 | Python | CC-BY-4.0 | D1 | Portable Lean 4 autoformalization skills and prompts for coding agents. |
| 27 | HIPREL-Group/VeriContest | https://github.com/HIPREL-Group/VeriContest | 14 | 2026-10-21 | Rust | Apache-2.0 | D1 | Verifiable competitive-programming benchmark with formal specifications, close to the dawnr task shape. |
| 28 | lfglabs-dev/rust-specification-generation-benchmark | https://github.com/lfglabs-dev/rust-specification-generation-benchmark | 0 | 2026-10-14 | Lean | Apache-2.0 | D1 | Lean 4 and Z3 specification generation tasks over extracted Rust code. |
| 29 | banr1/tailored-vericoding-benchmark | https://github.com/banr1/tailored-vericoding-benchmark | 0 | 2025-12-26 | Lean | MIT | D1 | Vericoding benchmark variant for spec-to-code tasks in verified languages; the API description is empty. |
| 30 | Smfakhoury/awesome-llm-specifications | https://github.com/Smfakhoury/awesome-llm-specifications | 0 | 2026-10-15 | Python | CC0-1.0 | D1 | Curated list of papers, benchmarks and tools on LLM-based specification inference and generation. |
| 31 | raymyers/awesome-verified-coding-agents | https://github.com/raymyers/awesome-verified-coding-agents | 7 | 2026-04-21 | unknown | CC0-1.0 | D1, D2 | Resource list on AI coding agents that use formal verification techniques. |
| 32 | midspiral/lemmascript-dafny-benchmark | https://github.com/midspiral/lemmascript-dafny-benchmark | 0 | 2026-09-27 | Dafny | NOASSERTION | D1 | Dafny proof-completion benchmark drawn from LemmaScript case studies. |
| 33 | crishN144/dafny-eval | https://github.com/crishN144/dafny-eval | 0 | 2026-08-17 | Python | unknown | D1 | Soundness-hardened benchmark for LLM Dafny invariant synthesis with semantic integrity gating. |
| 34 | Raj-Taware/specsaboteur | https://github.com/Raj-Taware/specsaboteur | 0 | 2026-05-24 | Python | MIT | D1 | Adversarial validation of formal specifications by generating implementations that expose specification gaps. |
| 35 | corpaci/SpecDrift | https://github.com/corpaci/SpecDrift | 1 | 2026-10-20 | Python | MIT | D1 | Measures whether specifications keep their meaning across LLM representations, a specification-quality check. |
| 36 | ChunyiLi322/NL2FLINLLM | https://github.com/ChunyiLi322/NL2FLINLLM | 0 | 2024-05-31 | Python | unknown | D1 | Formal specification generation through prompt-based LLMs, a specification-stage reference. |
| 37 | Eleanor-H/MUSTARD | https://github.com/Eleanor-H/MUSTARD | 43 | 2026-06-16 | C++ | unknown | D1 | Synthesis of theorem and proof data for LLM provers, a data-generation reference. |
| 38 | ibrahimmian36/leanscreen | https://github.com/ibrahimmian36/leanscreen | 7 | 2026-10-07 | Python | NOASSERTION | D1 | Faithfulness screen for informal and Lean 4 statement pairs, a specification-quality gate. |
| 39 | gpetiot/Frama-C-Mutation | https://github.com/gpetiot/Frama-C-Mutation | 20 | 2025-04-06 | OCaml | unknown | D1 | Generates mutant programs for Frama-C, a mutation source for checking that ACSL specifications reject bugs. |
| 40 | uw-math-ai/autoformalization-with-llms | https://github.com/uw-math-ai/autoformalization-with-llms | 8 | 2026-06-03 | Python | unknown | D1 | Autoformalization with LLMs; the API description is empty, so the fit is unverified. |
| 41 | epfl-lara/AutoformalizedProjects | https://github.com/epfl-lara/AutoformalizedProjects | 0 | 2026-09-08 | Lean | Apache-2.0 | D1 | Autonomous Lean formalizations of papers produced by an agent harness, an autoformalization example set. |
| 42 | XiangyuG/SpecGen | https://github.com/XiangyuG/SpecGen | 0 | 2025-11-26 | Python | unknown | D1 | Generates Rosette specifications with an LLM, a specification-stage reference. |
| 43 | AbdelbasetKABOU/CASP-LLM-Verification-Study | https://github.com/AbdelbasetKABOU/CASP-LLM-Verification-Study | 0 | 2026-03-13 | Python | unknown | D1 | Benchmarks LLMs on formal specification generation and scores the specifications with Frama-C. |
| 44 | namin/dafny-sketcher | https://github.com/namin/dafny-sketcher | 18 | 2026-07-31 | Dafny | MIT | D1, D2 | Interactive, semi-automated verified program synthesis built on the Dafny implementation. |
| 45 | Z3Prover/z3 | https://github.com/Z3Prover/z3 | 12805 | 2026-10-21 | C++ | NOASSERTION | D2 | Z3 SMT solver; model extraction supplies the counterexamples that error-to-feedback loops need. |
| 46 | cvc5/cvc5 | https://github.com/cvc5/cvc5 | 1375 | 2026-10-21 | SMT | NOASSERTION | D2 | cvc5 SMT solver; its countermodels are a second source of counterexample feedback. |
| 47 | boogie-org/boogie | https://github.com/boogie-org/boogie | 603 | 2026-10-12 | Boogie | MIT | D2 | Boogie intermediate verifier; its counterexample traces feed Dafny-style repair loops. |
| 48 | lean-dojo/LeanDojo | https://github.com/lean-dojo/LeanDojo | 848 | 2026-10-20 | Python | MIT | D2 | Lean data extraction and programmatic interaction toolkit for training and evaluating provers. |
| 49 | lean-dojo/ReProver | https://github.com/lean-dojo/ReProver | 339 | 2026-10-13 | Python | MIT | D2 | Retrieval-augmented Lean prover with premise selection and released models, a baseline for repair loops. |
| 50 | lean-dojo/LeanCopilot | https://github.com/lean-dojo/LeanCopilot | 1335 | 2026-10-19 | C++ | MIT | D2, D7 | LLM tactic suggestions and premise retrieval inside Lean, with local models served through CTranslate2. |
| 51 | lean-dojo/LeanDojoChatGPT | https://github.com/lean-dojo/LeanDojoChatGPT | 126 | 2026-10-18 | Python | MIT | D2 | ChatGPT plugin on top of LeanDojo, a thin interface to the Lean interaction layer. |
| 52 | lean-dojo/LeanAgent | https://github.com/lean-dojo/LeanAgent | 88 | 2026-10-20 | Python | unknown | D2 | Lifelong-learning agent for formal theorem proving in Lean. |
| 53 | lean-dojo/LeanDojo-v2 | https://github.com/lean-dojo/LeanDojo-v2 | 147 | 2026-10-16 | Python | Apache-2.0 | D2, D3 | Framework for training, evaluating and deploying AI-assisted Lean provers. |
| 54 | lean-dojo/LeanProgress | https://github.com/lean-dojo/LeanProgress | 5 | 2026-07-07 | Python | MIT | D2 | Proof progress prediction that guides neural proof search. |
| 55 | leanprover/Pantograph | https://github.com/leanprover/Pantograph | 84 | 2026-10-20 | Lean | Apache-2.0 | D2 | Machine-to-machine Lean 4 interface for proof execution and state inspection. |
| 56 | stanford-centaur/PyPantograph | https://github.com/stanford-centaur/PyPantograph | 150 | 2026-10-20 | Python | Apache-2.0 | D2 | Python API and REPL for training and evaluating Lean theorem-proving agents. |
| 57 | leanprover-community/repl | https://github.com/leanprover-community/repl | 235 | 2026-10-19 | Lean | Apache-2.0 | D2 | Lean REPL that reports errors and sorries, the standard interface behind LLM proof loops. |
| 58 | oOo0oOo/lean-lsp-mcp | https://github.com/oOo0oOo/lean-lsp-mcp | 531 | 2026-10-20 | Python | MIT | D2 | MCP server exposing Lean language-server feedback to coding agents. |
| 59 | project-numina/lean-lsp-mcp | https://github.com/project-numina/lean-lsp-mcp | 21 | 2026-08-28 | Python | MIT | D2 | Lean language-server MCP server for agent feedback loops; the API description is empty. |
| 60 | project-numina/kimina-lean-server | https://github.com/project-numina/kimina-lean-server | 212 | 2026-09-30 | Python | MIT | D2 | Lean verification server for batched checking of LLM-generated proofs, tied to Kimina-Prover tooling. |
| 61 | cameronfreer/lean4-skills | https://github.com/cameronfreer/lean4-skills | 466 | 2026-10-20 | Python | MIT | D2 | Lean 4 proving skills and workflow pack for AI coding agents. |
| 62 | cmu-l3/llmlean | https://github.com/cmu-l3/llmlean | 214 | 2026-10-20 | Lean | MIT | D2, D7 | LLM tactic suggestions for Lean that run on a laptop or in the cloud. |
| 63 | frenzymath/Archon | https://github.com/frenzymath/Archon | 227 | 2026-10-19 | Python | Apache-2.0 | D2 | AI-assisted Lean project automation with proof orchestration and multi-agent proving. |
| 64 | kAIto47802/Prover-Agent | https://github.com/kAIto47802/Prover-Agent | 33 | 2026-10-17 | Python | MIT | D2 | Agent-based framework for formal mathematical proofs. |
| 65 | YuanheZ/LeanMarathon | https://github.com/YuanheZ/LeanMarathon | 30 | 2026-10-05 | Python | Apache-2.0 | D1, D2 | Agent harness for long-horizon autoformalization, with graph-based work planning. |
| 66 | DebarghaG/proofofthought | https://github.com/DebarghaG/proofofthought | 377 | 2026-10-08 | Python | MIT | D2 | LLM reasoning checked by Z3 with SMT2 and JSON backends, a verifier-in-the-loop design. |
| 67 | wiio12/LEGO-Prover | https://github.com/wiio12/LEGO-Prover | 68 | 2026-07-26 | Python | MIT | D2, D3 | Neural theorem proving with a growing library of lemmas, a prover-loop reference. |
| 68 | haoxiongliu/ProofAug | https://github.com/haoxiongliu/ProofAug | 16 | 2026-06-30 | Python | unknown | D2 | Proof structure analysis for neural theorem proving, a feedback-driven proof search. |
| 69 | riyazahuja/ImProver | https://github.com/riyazahuja/ImProver | 44 | 2026-09-09 | Python | unknown | D2 | Agent-based automated proof optimization loop. |
| 70 | verse-lab/sisyphus | https://github.com/verse-lab/sisyphus | 16 | 2026-07-17 | OCaml | AGPL-3.0 | D2 | Mostly automated proof repair for verified libraries. |
| 71 | Axiomatic-AI/ax-prover-base | https://github.com/Axiomatic-AI/ax-prover-base | 52 | 2026-10-16 | Python | AGPL-3.0 | D2 | Minimal agent for automated theorem proving, with proofs checked by Lean. |
| 72 | trishullab/copra | https://github.com/trishullab/copra | 81 | 2026-10-15 | Python | unknown | D2 | In-context proof agent that prompts LLMs to prove formal theorems. |
| 73 | trishullab/proof-wala | https://github.com/trishullab/proof-wala | 9 | 2025-05-07 | Python | unknown | D2 | Library for proof-environment interaction, proof search and training of proof-step predictors. |
| 74 | kfdong/STP | https://github.com/kfdong/STP | 123 | 2026-09-03 | Python | MIT | D2, D3 | Self-play theorem provers with iterative conjecturing and proving. |
| 75 | zhehou/llm-isabelle | https://github.com/zhehou/llm-isabelle | 16 | 2026-10-17 | Python | MIT | D2 | LLM-powered theorem proving for Isabelle/HOL. |
| 76 | kappelmann/isabelle-pide-mcp | https://github.com/kappelmann/isabelle-pide-mcp | 19 | 2026-10-19 | Scala | LGPL-3.0 | D2 | MCP server for Isabelle/PIDE that gives agents proof-state feedback. |
| 77 | namin/dafny-mcp | https://github.com/namin/dafny-mcp | 3 | 2026-04-24 | Python | MIT | D2 | Dafny verifier exposed through MCP so agents can read verification output. |
| 78 | microsoft/verus-copilot-vscode | https://github.com/microsoft/verus-copilot-vscode | 18 | 2026-10-10 | Rust | MIT | D2 | Verus VS Code assistant from Microsoft; the API description is empty, so the feature set is unverified. |
| 79 | ChuyueSun/CryptoProver-core | https://github.com/ChuyueSun/CryptoProver-core | 3 | 2026-08-22 | Python | MIT | D2 | Slim Verus proof-synthesis agent that replaces admit calls with proofs that pass the build. |
| 80 | daphne-zhukeyu/verusage-handsoff-eval | https://github.com/daphne-zhukeyu/verusage-handsoff-eval | 0 | 2026-07-30 | Rust | unknown | D2 | Evaluation of a Verus proof-repair method on sampled VeruSAGE-Bench tasks. |
| 81 | asterinas/KVerus | https://github.com/asterinas/KVerus | 27 | 2026-10-16 | Python | MIT | D2 | Verus proof generation with error triage and knowledge-base repair prompts. |
| 82 | epfl-lara/LeanProbe | https://github.com/epfl-lara/LeanProbe | 6 | 2026-10-20 | Python | MIT | D2 | Fast Lean 4 proof feedback for coding agents through a CLI, a Python library and an MCP server. |
| 83 | hguitar762-bit/LeanProofAgent | https://github.com/hguitar762-bit/LeanProofAgent | 0 | 2026-09-28 | Python | MIT | D2 | Lean reasoning with compiler-guided repair and lightweight Mathlib premise retrieval. |
| 84 | Lean-Prover/lean-prover | https://github.com/Lean-Prover/lean-prover | 2 | 2026-10-19 | Python | unknown | D2 | Lean 4 agent that repairs LLM-drafted proofs against compiler diagnostics. |
| 85 | zfhuang99/lamport-agent | https://github.com/zfhuang99/lamport-agent | 16 | 2026-07-30 | TLA | MIT | D2 | Formal verification agent for designs or implementations with a checker feedback loop. |
| 86 | BartoszPiotrowski/lean-premise-selection | https://github.com/BartoszPiotrowski/lean-premise-selection | 23 | 2026-08-08 | Lean | unknown | D2 | Premise selection for Lean, a retrieval step for proof agents; the API description is empty. |
| 87 | LLM4Rocq/rocq-mcp | https://github.com/LLM4Rocq/rocq-mcp | 47 | 2026-10-19 | Python | Apache-2.0 | D2 | MCP server for the Rocq prover. |
| 88 | scidonia/rocq-piler | https://github.com/scidonia/rocq-piler | 9 | 2026-10-14 | Rocq Prover | Apache-2.0 | D2 | MCP server for the Coq language server, giving agents proof feedback. |
| 89 | angrysky56/mcp-rocq | https://github.com/angrysky56/mcp-rocq | 10 | 2026-05-02 | Python | MIT | D2 | Rocq/Coq reasoning server for agent use. |
| 90 | JetBrains-Research/coqpilot | https://github.com/JetBrains-Research/coqpilot | 130 | 2026-10-05 | TypeScript | LGPL-2.1 | D2 | VS Code plugin that fills Coq admits with LLM candidates checked by Coq. |
| 91 | princeton-vl/CoqGym | https://github.com/princeton-vl/CoqGym | 422 | 2026-10-20 | Coq | LGPL-2.1 | D2 | Learning environment for Coq theorem proving with a tactic-prediction agent. |
| 92 | coq-tactician/coq-tactician | https://github.com/coq-tactician/coq-tactician | 87 | 2026-10-08 | OCaml | MIT | D2 | Interactive tactic learner and prover for Coq. |
| 93 | tom-p-reichel/proof-repair-tool | https://github.com/tom-p-reichel/proof-repair-tool | 3 | 2025-02-04 | Python | unknown | D2 | Coq proof repair with a fine-tuned LLM, a theorem vector store and proof-tree search. |
| 94 | uwplse/pumpkin-pi | https://github.com/uwplse/pumpkin-pi | 50 | 2026-08-04 | Coq | MIT | D2 | Proof repair across type equivalences in Coq, a non-LLM repair reference. |
| 95 | monkeytim19/proof-repair-LLM-Lean4 | https://github.com/monkeytim19/proof-repair-LLM-Lean4 | 2 | 2025-05-02 | Jupyter Notebook | unknown | D2 | LLM proof repair for Lean 4; the API description is empty. |
| 96 | gokdeniz-cakir/llm-lean-proof-repair | https://github.com/gokdeniz-cakir/llm-lean-proof-repair | 0 | 2025-12-29 | unknown | unknown | D2 | Study of how well LLMs diagnose and repair faulty Lean 4 proofs. |
| 97 | rkthomps/coq-modeling | https://github.com/rkthomps/coq-modeling | 32 | 2026-10-17 | Jupyter Notebook | MIT | D2 | Language models for Coq trained on data collected from the Coq language server. |
| 98 | rkthomps/CoqStoq | https://github.com/rkthomps/CoqStoq | 12 | 2026-10-05 | Python | unknown | D2 | Benchmark for evaluating Coq proof search tools. |
| 99 | cherrysowmya/Open-Weight-Multi-Agent-Formal-Math-Reasoning-System | https://github.com/cherrysowmya/Open-Weight-Multi-Agent-Formal-Math-Reasoning-System | 0 | 2026-09-23 | Python | unknown | D2, D7 | Fully local open-weight multi-agent theorem proving with Qwen3, Lean 4 and Mathlib. |
| 100 | SkyShannonProver/shannon-prover | https://github.com/SkyShannonProver/shannon-prover | 23 | 2026-10-14 | Python | NOASSERTION | D2 | LLM agents that write machine-checked cryptographic proofs in EasyCrypt. |
| 101 | agentic-prover/aprover | https://github.com/agentic-prover/aprover | 19 | 2026-10-20 | Python | NOASSERTION | D2 | Agentic prover for AI-generated code that combines LLM agents with bounded model checking. |
| 102 | noahshinn/reflexion | https://github.com/noahshinn/reflexion | 3313 | 2026-10-20 | Python | MIT | D2 | Verbal reinforcement from test and error feedback, a repair-loop reference. |
| 103 | Codium-ai/AlphaCodium | https://github.com/Codium-ai/AlphaCodium | 3966 | 2026-10-20 | Python | AGPL-3.0 | D2 | Test-driven iterative code generation flow, relevant to the write-then-run stage. |
| 104 | salesforce/CodeRL | https://github.com/salesforce/CodeRL | 578 | 2026-10-16 | Python | BSD-3-Clause | D2, D3 | Actor-critic RL for code generation that uses unit-test feedback as the reward signal. |
| 105 | cmu-l3/Leanimum-agent | https://github.com/cmu-l3/Leanimum-agent | 11 | 2026-10-21 | Python | NOASSERTION | D2 | Compact AI agent for proving theorems and writing programs in Lean. |
| 106 | mike1729/BurnQED | https://github.com/mike1729/BurnQED | 1 | 2026-09-04 | Rust | Apache-2.0 | D2 | Lean 4 prover pairing an LLM policy with an energy-based value model, trained by expert iteration. |
| 107 | kanav9063/CoProver | https://github.com/kanav9063/CoProver | 0 | 2026-09-12 | Python | unknown | D2, D3 | Co-training of proof generation and search heuristics for Lean 4 theorem proving. |
| 108 | levineuwirth/proof-broker | https://github.com/levineuwirth/proof-broker | 0 | 2026-10-09 | Python | MIT | D2 | Certificate boundary for untrusted proof search with Lean 4 and Rocq goals. |
| 109 | rayyanaamir22/TinyProof-Prover | https://github.com/rayyanaamir22/TinyProof-Prover | 2 | 2026-02-27 | Jupyter Notebook | unknown | D2, D3 | LLM-guided Lean 4 prover with Monte Carlo tree search and RL components. |
| 110 | charlesmsiegel/hardy | https://github.com/charlesmsiegel/hardy | 2 | 2026-10-18 | Python | Apache-2.0 | D2 | Lean 4 theorem-proving harness with formalizations frozen before proving and independent verification. |
| 111 | anetigone/cssc | https://github.com/anetigone/cssc | 1 | 2026-07-19 | Python | unknown | D2 | Cost-sensitive search control for LLM-guided formal proof agents. |
| 112 | dududuguo/lean-local-search-mcp | https://github.com/dududuguo/lean-local-search-mcp | 1 | 2026-07-19 | Python | MIT | D2 | MCP server for local Lean and Mathlib theorem search with proof probes. |
| 113 | RIvance/lean4-mcp | https://github.com/RIvance/lean4-mcp | 8 | 2026-10-03 | Rust | MIT | D2 | MCP proxy between AI agents and the Lean 4 language server. |
| 114 | VeryMath/AI4Math-Lean-Agents | https://github.com/VeryMath/AI4Math-Lean-Agents | 9 | 2026-10-09 | Python | MIT | D2 | Lean 4 formalization skills and workflows including proof repair. |
| 115 | padieul/tactic-annot | https://github.com/padieul/tactic-annot | 0 | 2025-12-12 | Jupyter Notebook | unknown | D2 | LLM-guided Aesop tactic strategies for Lean 4, logging successful proofs. |
| 116 | huggingface/trl | https://github.com/huggingface/trl | 19559 | 2026-10-21 | Python | Apache-2.0 | D3 | Hugging Face RL trainers for LLMs, including GRPO and custom reward functions. |
| 117 | verl-project/verl | https://github.com/verl-project/verl | 23954 | 2026-10-21 | Python | Apache-2.0 | D3 | RL post-training framework for LLMs with GRPO and PPO options. |
| 118 | OpenRLHF/OpenRLHF | https://github.com/OpenRLHF/OpenRLHF | 10103 | 2026-10-21 | Python | Apache-2.0 | D3 | Ray-based RL framework for LLMs with PPO and DAPO options. |
| 119 | NovaSky-AI/SkyRL | https://github.com/NovaSky-AI/SkyRL | 2440 | 2026-10-21 | Python | Apache-2.0 | D3 | Modular full-stack RL library for LLMs with code, math and tool-use environments. |
| 120 | areal-project/AReaL | https://github.com/areal-project/AReaL | 5862 | 2026-10-21 | Python | Apache-2.0 | D3 | Asynchronous RL system for LLM agents and reasoning training. |
| 121 | THUDM/slime | https://github.com/THUDM/slime | 8702 | 2026-10-21 | Python | Apache-2.0 | D3 | LLM training framework for RL scaling. |
| 122 | NVIDIA-NeMo/RL | https://github.com/NVIDIA-NeMo/RL | 2076 | 2026-10-21 | Python | Apache-2.0 | D3 | NVIDIA toolkit for model reinforcement learning, a training-stack reference. |
| 123 | PrimeIntellect-ai/prime-rl | https://github.com/PrimeIntellect-ai/prime-rl | 2185 | 2026-10-21 | Python | Apache-2.0 | D3 | Agentic RL training at scale. |
| 124 | PRIME-RL/PRIME | https://github.com/PRIME-RL/PRIME | 1871 | 2026-10-18 | Python | Apache-2.0 | D3 | Scalable RL solution for advanced reasoning of language models, using process rewards. |
| 125 | PrimeIntellect-ai/verifiers | https://github.com/PrimeIntellect-ai/verifiers | 4723 | 2026-10-21 | Python | MIT | D3 | Environments with rubrics and verifiable rewards for LLM RL training. |
| 126 | rllm-org/rllm | https://github.com/rllm-org/rllm | 5891 | 2026-10-20 | Python | Apache-2.0 | D3 | Open RL framework for LLM training and agents. |
| 127 | OpenPipe/ART | https://github.com/OpenPipe/ART | 10814 | 2026-10-21 | Python | Apache-2.0 | D3 | Agent Reinforcement Trainer for training multi-step agents. |
| 128 | unslothai/unsloth | https://github.com/unslothai/unsloth | 78336 | 2026-10-21 | Python | Apache-2.0 | D3, D7 | Low-VRAM fine-tuning and RL training for local models. |
| 129 | hiyouga/LlamaFactory | https://github.com/hiyouga/LlamaFactory | 75607 | 2026-10-21 | Python | Apache-2.0 | D3 | Fine-tuning framework covering 100+ LLMs and VLMs, a training-stack reference. |
| 130 | axolotl-ai-cloud/axolotl | https://github.com/axolotl-ai-cloud/axolotl | 12599 | 2026-10-21 | Python | Apache-2.0 | D3 | Fine-tuning toolkit for LLMs with LoRA and QLoRA recipes. |
| 131 | Lightning-AI/litgpt | https://github.com/Lightning-AI/litgpt | 13719 | 2026-10-21 | Python | Apache-2.0 | D3 | Recipes to pretrain, finetune and deploy 20+ LLMs. |
| 132 | meta-pytorch/torchtune | https://github.com/meta-pytorch/torchtune | 5819 | 2026-10-21 | Python | BSD-3-Clause | D3 | PyTorch-native post-training library with fine-tuning recipes. |
| 133 | artidoro/qlora | https://github.com/artidoro/qlora | 11050 | 2026-10-20 | Jupyter Notebook | MIT | D3 | QLoRA: 4-bit fine-tuning of quantized LLMs on one GPU, a low-VRAM training reference. |
| 134 | huggingface/peft | https://github.com/huggingface/peft | 21815 | 2026-10-21 | Python | Apache-2.0 | D3 | LoRA and parameter-efficient tuning library, a base layer for low-VRAM training. |
| 135 | bitsandbytes-foundation/bitsandbytes | https://github.com/bitsandbytes-foundation/bitsandbytes | 8529 | 2026-10-21 | Python | MIT | D3, D7 | k-bit quantization for PyTorch, enabling 4-bit and 8-bit training and inference on consumer GPUs. |
| 136 | linkedin/Liger-Kernel | https://github.com/linkedin/Liger-Kernel | 6664 | 2026-10-21 | Python | BSD-2-Clause | D3 | Triton kernels that reduce memory use in LLM training. |
| 137 | huggingface/open-r1 | https://github.com/huggingface/open-r1 | 26476 | 2026-10-21 | Python | Apache-2.0 | D3 | Open reproduction of DeepSeek-R1 training recipes, including the RL stage. |
| 138 | BytedTsinghua-SIA/DAPO | https://github.com/BytedTsinghua-SIA/DAPO | 1953 | 2026-10-21 | Python | unknown | D3 | DAPO open-source RL system for LLM reasoning, a GRPO variant; gh reports no licence. |
| 139 | Jiayi-Pan/TinyZero | https://github.com/Jiayi-Pan/TinyZero | 13252 | 2026-10-20 | Python | Apache-2.0 | D3 | Minimal reproduction of DeepSeek R1-Zero style RL, a low-cost reference. |
| 140 | hkust-nlp/simpleRL-reason | https://github.com/hkust-nlp/simpleRL-reason | 3880 | 2026-10-20 | Python | MIT | D3 | Simple RL training recipe for reasoning models. |
| 141 | Unakar/Logic-RL | https://github.com/Unakar/Logic-RL | 2452 | 2026-10-01 | Python | Apache-2.0 | D3 | Reproduces R1-Zero style RL on logic puzzles with rule-based rewards. |
| 142 | Open-Reasoner-Zero/Open-Reasoner-Zero | https://github.com/Open-Reasoner-Zero/Open-Reasoner-Zero | 2100 | 2026-10-13 | Python | MIT | D3 | Open zero-RL recipes for reasoning models. |
| 143 | McGill-NLP/nano-aha-moment | https://github.com/McGill-NLP/nano-aha-moment | 638 | 2026-10-19 | Jupyter Notebook | MIT | D3 | Single-file, single-GPU RL training written from scratch. |
| 144 | policy-gradient/GRPO-Zero | https://github.com/policy-gradient/GRPO-Zero | 1907 | 2026-10-18 | Python | Apache-2.0 | D3 | GRPO implemented from scratch, a small reference for the trainer loop. |
| 145 | lsdefine/simple_GRPO | https://github.com/lsdefine/simple_GRPO | 1714 | 2026-10-21 | Python | Apache-2.0 | D3 | Minimal GRPO implementation for R1-style reasoning training. |
| 146 | open-thought/reasoning-gym | https://github.com/open-thought/reasoning-gym | 1535 | 2026-10-19 | Python | Apache-2.0 | D3 | Procedural reasoning environments with programmatic verifiers for RL. |
| 147 | sileod/reasoning-core | https://github.com/sileod/reasoning-core | 51 | 2026-10-20 | Python | MIT | D3 | Procedural generators for verifiable reasoning data. |
| 148 | allenai/open-instruct | https://github.com/allenai/open-instruct | 3901 | 2026-10-21 | Python | Apache-2.0 | D3 | AllenAI post-training codebase, a reference for RL post-training pipelines. |
| 149 | SkyworkAI/Skywork-OR1 | https://github.com/SkyworkAI/Skywork-OR1 | 738 | 2026-10-15 | Python | Apache-2.0 | D3 | Open RL recipes for math and code reasoning models. |
| 150 | ypwang61/One-Shot-RLVR | https://github.com/ypwang61/One-Shot-RLVR | 451 | 2026-10-19 | Python | Apache-2.0 | D3 | RLVR research code built around single-example training, a low-cost RLVR reference. |
| 151 | chi2liu/ABC-GRPO | https://github.com/chi2liu/ABC-GRPO | 438 | 2026-10-13 | Python | Apache-2.0 | D3 | Bounded-clipping GRPO variant for reasoning RL. |
| 152 | knoveleng/open-rs | https://github.com/knoveleng/open-rs | 295 | 2026-09-26 | Python | MIT | D3 | Official repo for a reinforcement learning reasoning paper, with recipes to adapt. |
| 153 | anakin87/qwen-scheduler-grpo | https://github.com/anakin87/qwen-scheduler-grpo | 272 | 2026-10-15 | Jupyter Notebook | Apache-2.0 | D3 | GRPO training of a small Qwen model to produce structured schedules. |
| 154 | Zhiyuan-Zeng/RLVE | https://github.com/Zhiyuan-Zeng/RLVE | 251 | 2026-10-19 | Python | MIT | D3 | Scaling RL for language models with verifiable environments. |
| 155 | Oxen-AI/GRPO-With-Cargo-Feedback | https://github.com/Oxen-AI/GRPO-With-Cargo-Feedback | 119 | 2026-08-22 | Python | MIT | D2, D3 | GRPO fine-tuning with cargo compiler feedback as the reward for Rust code. |
| 156 | axolotl-ai-cloud/grpo_code | https://github.com/axolotl-ai-cloud/grpo_code | 42 | 2026-08-04 | Python | Apache-2.0 | D3 | GRPO approach for training code LLMs, described as local and secure. |
| 157 | KJLdefeated/RL.cu | https://github.com/KJLdefeated/RL.cu | 42 | 2026-07-25 | Cuda | MIT | D3 | RLVR training for LLMs written in CUDA C++, a compact trainer reference. |
| 158 | jackfsuia/nanoRLHF | https://github.com/jackfsuia/nanoRLHF | 81 | 2026-08-06 | Python | MIT | D3 | RLHF experiments on a single 40 GB GPU with PPO and GRPO. |
| 159 | pochenai/nano-llm-posttraining | https://github.com/pochenai/nano-llm-posttraining | 29 | 2026-10-04 | Python | MIT | D3 | Minimal post-training experiments that run on one 8 GB GPU. |
| 160 | cnsdqd-dyb/Guide-GRPO | https://github.com/cnsdqd-dyb/Guide-GRPO | 27 | 2026-10-02 | Python | MIT | D3 | GRPO with reduced memory use, aimed at 24 GB consumer GPUs. |
| 161 | vllm-project/vime | https://github.com/vllm-project/vime | 490 | 2026-10-19 | Python | Apache-2.0 | D3 | LLM post-training framework using vLLM for RL scaling. |
| 162 | Future-House/ether0 | https://github.com/Future-House/ether0 | 170 | 2026-10-19 | Python | Apache-2.0 | D3 | Scientific reasoning model with reward functions for chemistry, an example of task-specific verifier rewards. |
| 163 | DeepGym/deepgym | https://github.com/DeepGym/deepgym | 43 | 2026-10-19 | Python | NOASSERTION | D3 | RL environments with verifiable rewards and sandboxed scoring. |
| 164 | stanleyngugi/formally-verified-code-rl | https://github.com/stanleyngugi/formally-verified-code-rl | 0 | 2026-10-02 | Python | Apache-2.0 | D3 | RL environments that score generated code with formal verification. |
| 165 | cabloo/rlvr-lean | https://github.com/cabloo/rlvr-lean | 0 | 2026-10-12 | Python | unknown | D3 | RLVR for Lean proofs; the API description is empty. |
| 166 | AlanAkillove/TinyLean-RL | https://github.com/AlanAkillove/TinyLean-RL | 0 | 2026-09-15 | Python | MIT | D3 | Compute-conscious RL for sub-billion-parameter Lean provers. |
| 167 | Leanabell-LM/Leanabell-Prover | https://github.com/Leanabell-LM/Leanabell-Prover | 12 | 2025-12-02 | unknown | unknown | D2, D3 | RL training of a Lean prover to elicit reflective reasoning. |
| 168 | smiles724/Awesome-LLM-RLVR | https://github.com/smiles724/Awesome-LLM-RLVR | 143 | 2026-10-19 | Python | MIT | D3 | Curated papers and materials on reinforcement learning with verifiable rewards. |
| 169 | Mohammadjafari80/GSM8K-RLVR | https://github.com/Mohammadjafari80/GSM8K-RLVR | 172 | 2026-08-14 | Python | unknown | D3 | Small RLVR experiments on GSM8K. |
| 170 | TeenLucifer/grpo_reproduce | https://github.com/TeenLucifer/grpo_reproduce | 172 | 2026-10-09 | Python | unknown | D3 | Comparison of GRPO and GSPO on a 1.5B Qwen model. |
| 171 | CarperAI/trlx | https://github.com/CarperAI/trlx | 4756 | 2026-10-18 | Python | MIT | D3 | Distributed RL fine-tuning of language models. |
| 172 | ByteDance-Seed/Seed-Prover | https://github.com/ByteDance-Seed/Seed-Prover | 441 | 2026-10-08 | Lean | Apache-2.0 | D3, D7 | Lean prover system from ByteDance Seed; the API description is empty. |
| 173 | deepseek-ai/DeepSeek-Prover-V1.5 | https://github.com/deepseek-ai/DeepSeek-Prover-V1.5 | 588 | 2026-10-21 | Python | MIT | D3, D7 | Lean 4 prover model repository from DeepSeek; the API description is empty. |
| 174 | Goedel-LM/Goedel-Prover | https://github.com/Goedel-LM/Goedel-Prover | 240 | 2026-10-18 | Python | MIT | D3, D7 | Lean 4 prover models and data for formal math proofs, a prover-side comparison point. |
| 175 | MoonshotAI/Kimina-Prover-Preview | https://github.com/MoonshotAI/Kimina-Prover-Preview | 378 | 2026-10-20 | Python | unknown | D3, D7 | Technical report repository for Kimina-Prover, a Lean 4 prover trained with RL. |
| 176 | stepfun-ai/StepFun-Prover-Preview | https://github.com/stepfun-ai/StepFun-Prover-Preview | 33 | 2026-06-30 | unknown | Apache-2.0 | D3, D7 | LLMs for formal theorem proving through tool-integrated reasoning. |
| 177 | modelscope/ms-swift | https://github.com/modelscope/ms-swift | 15899 | 2026-10-21 | Python | Apache-2.0 | D3 | Fine-tuning framework with PEFT and GRPO support for 600+ LLMs. |
| 178 | PeterGriffinJin/Search-R1 | https://github.com/PeterGriffinJin/Search-R1 | 5528 | 2026-10-21 | Python | Apache-2.0 | D3 | RL training framework for reasoning with search-engine calls. |
| 179 | SWE-Gym/SWE-Gym | https://github.com/SWE-Gym/SWE-Gym | 750 | 2026-10-18 | Jupyter Notebook | Apache-2.0 | D3 | Environment for training software engineering agents and verifiers on test outcomes. |
| 180 | SWE-bench/SWE-smith | https://github.com/SWE-bench/SWE-smith | 810 | 2026-10-20 | Python | MIT | D3 | Data scaling pipeline for training software engineering agents. |
| 181 | TianHongZXY/RLVR-Decomposed | https://github.com/TianHongZXY/RLVR-Decomposed | 173 | 2026-10-12 | Python | Apache-2.0 | D3 | Implementation of RLVR experiments on the effect of negative reinforcement. |
| 182 | THUDM/TreeRL | https://github.com/THUDM/TreeRL | 106 | 2026-09-28 | Python | Apache-2.0 | D3 | LLM RL with on-policy tree search. |
| 183 | AMAP-ML/Tree-GRPO | https://github.com/AMAP-ML/Tree-GRPO | 407 | 2026-10-19 | Python | Apache-2.0 | D3 | Tree search for LLM agent reinforcement learning. |
| 184 | mit-han-lab/fastrl | https://github.com/mit-han-lab/fastrl | 184 | 2026-10-20 | Python | Apache-2.0 | D3 | Reasoning RL training system with a long-tail focus, from the ASPLOS 2026 paper. |
| 185 | warlockee/oxRL | https://github.com/warlockee/oxRL | 20 | 2026-08-10 | Python | Apache-2.0 | D3 | Post-training framework for LLMs and VLMs with many algorithms and verified models. |
| 186 | psrl-project/psrl | https://github.com/psrl-project/psrl | 14 | 2026-10-20 | Python | Apache-2.0 | D3 | Asynchronous RL framework for LLM post-training. |
| 187 | Minami-su/deepspeed-grpo-qlora-vllm | https://github.com/Minami-su/deepspeed-grpo-qlora-vllm | 13 | 2026-01-29 | Python | Apache-2.0 | D3 | GRPO with QLoRA and vLLM under DeepSpeed. |
| 188 | Bharath2/Minimal-GRPO | https://github.com/Bharath2/Minimal-GRPO | 9 | 2026-03-10 | Python | MIT | D3 | Minimal GRPO fine-tuning of open language models with verifiable rewards. |
| 189 | nancui0000/adaptive-mogrpo | https://github.com/nancui0000/adaptive-mogrpo | 49 | 2026-10-10 | Python | unknown | D3 | Adaptive weight scheduling for multi-objective GRPO in code generation. |
| 190 | jayminbhan/RLVR-vs-SFT-Qwen2.5-1.5b | https://github.com/jayminbhan/RLVR-vs-SFT-Qwen2.5-1.5b | 13 | 2026-09-12 | Python | Apache-2.0 | D3 | SFT and GRPO-based RLVR compared on a 1.5B model with GSM8K. |
| 191 | ggml-org/llama.cpp | https://github.com/ggml-org/llama.cpp | 131870 | 2026-10-21 | C++ | MIT | D7 | LLM inference in C/C++ with GBNF grammars and GGUF quantized models. |
| 192 | abetlen/llama-cpp-python | https://github.com/abetlen/llama-cpp-python | 10650 | 2026-10-20 | Python | MIT | D7 | Python bindings for llama.cpp with grammar-constrained sampling. |
| 193 | ggml-org/ggml | https://github.com/ggml-org/ggml | 15513 | 2026-10-21 | C++ | MIT | D7 | Tensor library underneath llama.cpp. |
| 194 | vllm-project/vllm | https://github.com/vllm-project/vllm | 94512 | 2026-10-21 | Python | Apache-2.0 | D7 | High-throughput serving engine, a serving reference with structured-output and speculative-decoding features. |
| 195 | sgl-project/sglang | https://github.com/sgl-project/sglang | 37534 | 2026-10-21 | Python | Apache-2.0 | D7 | High-performance serving framework for LLMs, a serving reference with constrained decoding. |
| 196 | mlc-ai/mlc-llm | https://github.com/mlc-ai/mlc-llm | 23261 | 2026-10-21 | Python | Apache-2.0 | D7 | Universal LLM deployment engine with ML compilation. |
| 197 | guidance-ai/guidance | https://github.com/guidance-ai/guidance | 21804 | 2026-10-21 | Jupyter Notebook | MIT | D7 | Guidance language for controlling LLM generation with constraints. |
| 198 | guidance-ai/llguidance | https://github.com/guidance-ai/llguidance | 892 | 2026-10-20 | Rust | MIT | D7 | Structured-output engine behind guidance, also wired into llama.cpp. |
| 199 | dottxt-ai/outlines | https://github.com/dottxt-ai/outlines | 15962 | 2026-10-21 | Python | Apache-2.0 | D7 | Structured generation that constrains output to JSON schemas and regex. |
| 200 | mlc-ai/xgrammar | https://github.com/mlc-ai/xgrammar | 1968 | 2026-10-21 | Python | Apache-2.0 | D7 | Structured generation engine for grammar-constrained decoding. |
| 201 | 1rgs/jsonformer | https://github.com/1rgs/jsonformer | 4938 | 2026-10-20 | Jupyter Notebook | MIT | D7 | Structured JSON generation by controlling the decoder. |
| 202 | noamgat/lm-format-enforcer | https://github.com/noamgat/lm-format-enforcer | 2041 | 2026-10-05 | Python | MIT | D7 | Enforces JSON Schema or regex output formats during decoding. |
| 203 | eth-sri/lmql | https://github.com/eth-sri/lmql | 4223 | 2026-10-17 | Python | Apache-2.0 | D7 | Query language for constraint-guided LLM programming. |
| 204 | kanishkg/synchromesh | https://github.com/kanishkg/synchromesh | 33 | 2026-06-07 | Python | MIT | D7 | Open implementation of constrained decoding that keeps generations in a required format. |
| 205 | epfl-dlab/transformers-CFG | https://github.com/epfl-dlab/transformers-CFG | 140 | 2026-09-29 | Python | MIT | D7 | Context-free grammar constrained decoding for Hugging Face Transformers. |
| 206 | microsoft/aici | https://github.com/microsoft/aici | 2076 | 2026-10-13 | Rust | MIT | D7 | Controller framework running WebAssembly programs to constrain token generation. |
| 207 | turboderp-org/exllamav2 | https://github.com/turboderp-org/exllamav2 | 4639 | 2026-10-20 | Python | MIT | D7 | Local inference library for quantized LLMs on consumer GPUs. |
| 208 | EricLBuehler/mistral.rs | https://github.com/EricLBuehler/mistral.rs | 7761 | 2026-10-21 | Rust | MIT | D7 | Rust LLM inference engine, a serving option for quantized small models. |
| 209 | huggingface/candle | https://github.com/huggingface/candle | 21208 | 2026-10-21 | Rust | Apache-2.0 | D7 | Minimalist Rust ML framework with LLM examples. |
| 210 | mozilla-ai/llamafile | https://github.com/mozilla-ai/llamafile | 26447 | 2026-10-21 | C++ | NOASSERTION | D7 | Single-file distribution and runtime for running LLMs locally. |
| 211 | huggingface/text-generation-inference | https://github.com/huggingface/text-generation-inference | 10880 | 2026-10-20 | Python | Apache-2.0 | D7 | Text generation server for LLMs, a serving reference with quantization options. |
| 212 | NVIDIA/TensorRT-LLM | https://github.com/NVIDIA/TensorRT-LLM | 14891 | 2026-10-21 | Python | NOASSERTION | D7 | GPU inference engine for LLMs with a Python API, a serving option on NVIDIA hardware. |
| 213 | FasterDecoding/Medusa | https://github.com/FasterDecoding/Medusa | 2775 | 2026-10-16 | Jupyter Notebook | Apache-2.0 | D7 | Multi-head speculative decoding for faster generation from one model. |
| 214 | SafeAILab/EAGLE | https://github.com/SafeAILab/EAGLE | 2557 | 2026-10-20 | Python | NOASSERTION | D7 | Official EAGLE-1, EAGLE-2 and EAGLE-3 speculative decoding code. |
| 215 | deepseek-ai/DeepSpec | https://github.com/deepseek-ai/DeepSpec | 7237 | 2026-10-21 | Python | MIT | D7 | Codebase for training and evaluating speculative decoding algorithms. |
| 216 | z-lab/dflash | https://github.com/z-lab/dflash | 6185 | 2026-10-20 | Python | MIT | D7 | Block-diffusion draft model for speculative decoding. |
| 217 | hao-ai-lab/LookaheadDecoding | https://github.com/hao-ai-lab/LookaheadDecoding | 1343 | 2026-10-13 | Python | Apache-2.0 | D7 | Lookahead decoding that breaks sequential dependency without a draft model. |
| 218 | apoorvumang/prompt-lookup-decoding | https://github.com/apoorvumang/prompt-lookup-decoding | 618 | 2026-10-10 | Jupyter Notebook | unknown | D7 | Draft-free speculative decoding that reuses n-grams from the prompt. |
| 219 | feifeibear/LLMSpeculativeSampling | https://github.com/feifeibear/LLMSpeculativeSampling | 927 | 2026-10-12 | Python | Apache-2.0 | D7 | Speculative sampling implementation for LLM decoding. |
| 220 | FasterDecoding/REST | https://github.com/FasterDecoding/REST | 220 | 2026-09-04 | C | Apache-2.0 | D7 | Retrieval-based speculative decoding. |
| 221 | sgl-project/SpecForge | https://github.com/sgl-project/SpecForge | 1229 | 2026-10-20 | Python | MIT | D7 | Training framework for speculative decoding draft models served by SGLang. |
| 222 | Infini-AI-Lab/Sequoia | https://github.com/Infini-AI-Lab/Sequoia | 375 | 2026-10-05 | Python | unknown | D7 | Tree-based speculative decoding algorithm. |
| 223 | ikawrakow/ik_llama.cpp | https://github.com/ikawrakow/ik_llama.cpp | 3316 | 2026-10-21 | C++ | MIT | D7 | llama.cpp fork with additional quantization formats and performance work. |
| 224 | ggml-org/llama.vscode | https://github.com/ggml-org/llama.vscode | 1546 | 2026-10-19 | TypeScript | MIT | D7 | Editor completion plugin backed by llama.cpp. |
| 225 | withcatai/node-llama-cpp | https://github.com/withcatai/node-llama-cpp | 2192 | 2026-10-20 | TypeScript | MIT | D7 | Node.js bindings for llama.cpp, including JSON-schema enforcement. |
| 226 | IST-DASLab/gptq | https://github.com/IST-DASLab/gptq | 2386 | 2026-10-16 | Python | Apache-2.0 | D7 | GPTQ post-training quantization for LLMs. |
| 227 | AutoGPTQ/AutoGPTQ | https://github.com/AutoGPTQ/AutoGPTQ | 5067 | 2026-10-20 | Python | MIT | D7 | GPTQ quantization package with simple APIs. |
| 228 | casper-hansen/AutoAWQ | https://github.com/casper-hansen/AutoAWQ | 2344 | 2026-10-20 | Python | MIT | D7 | 4-bit AWQ quantization package. |
| 229 | mit-han-lab/llm-awq | https://github.com/mit-han-lab/llm-awq | 3652 | 2026-10-19 | Python | MIT | D7 | Activation-aware weight quantization for LLM compression and acceleration. |
| 230 | vllm-project/llm-compressor | https://github.com/vllm-project/llm-compressor | 3893 | 2026-10-21 | Python | Apache-2.0 | D7 | LLM compression library for quantized inference with vLLM. |
| 231 | pytorch/ao | https://github.com/pytorch/ao | 3011 | 2026-10-20 | Python | NOASSERTION | D7 | PyTorch-native quantization for training and inference. |
| 232 | microsoft/BitNet | https://github.com/microsoft/BitNet | 41220 | 2026-10-21 | C++ | MIT | D7 | Official inference framework for 1-bit LLMs. |
| 233 | kvcache-ai/ktransformers | https://github.com/kvcache-ai/ktransformers | 19618 | 2026-10-21 | Python | Apache-2.0 | D7 | Heterogeneous CPU-GPU inference framework for large models. |
| 234 | LMCache/LMCache | https://github.com/LMCache/LMCache | 12133 | 2026-10-21 | Python | Apache-2.0 | D7 | KV cache layer for LLM serving. |
| 235 | mostlygeek/llama-swap | https://github.com/mostlygeek/llama-swap | 6033 | 2026-10-21 | Go | MIT | D7 | Model-swapping proxy for llama.cpp and other local OpenAI-compatible servers. |
| 236 | ollama/ollama | https://github.com/ollama/ollama | 184097 | 2026-10-21 | Go | MIT | D7 | Local model runtime and server with GGUF import, a serving baseline. |
| 237 | antirez/gguf-tools | https://github.com/antirez/gguf-tools | 370 | 2026-10-20 | C | MIT | D7 | GGUF implementation in C as a library and command-line tools. |
| 238 | iuliaturc/gguf-docs | https://github.com/iuliaturc/gguf-docs | 522 | 2026-10-08 | unknown | MIT | D7 | Unofficial documentation for GGUF quantization. |
| 239 | IohannesArnold/xml_gbnf | https://github.com/IohannesArnold/xml_gbnf | 6 | 2026-07-14 | unknown | 0BSD | D7 | GBNF grammar for XML output, usable with llama.cpp. |
| 240 | QwenLM/Qwen3 | https://github.com/QwenLM/Qwen3 | 27678 | 2026-10-21 | Python | unknown | D7 | Qwen3 model series, the family behind the 4B-class base model of dawnr. |
| 241 | deepseek-ai/DeepSeek-Prover-V2 | https://github.com/deepseek-ai/DeepSeek-Prover-V2 | 1314 | 2026-10-21 | unknown | NOASSERTION | D7, D3 | Lean 4 prover model repository from DeepSeek; licence reported as other, so check the model terms. |
| 242 | deepseek-ai/DeepSeek-Coder | https://github.com/deepseek-ai/DeepSeek-Coder | 24302 | 2026-10-21 | Python | MIT | D7 | Code model family from DeepSeek under an MIT repository licence. |
| 243 | lyogavin/airllm | https://github.com/lyogavin/airllm | 39953 | 2026-10-21 | Jupyter Notebook | Apache-2.0 | D7 | Layer-by-layer inference for very large models on a single small GPU. |
| 244 | xjdr-alt/entropix | https://github.com/xjdr-alt/entropix | 3430 | 2026-10-16 | Python | Apache-2.0 | D7 | Entropy-based sampling and parallel chain-of-thought decoding. |
| 245 | algorithmicsuperintelligence/optillm | https://github.com/algorithmicsuperintelligence/optillm | 4324 | 2026-10-20 | Python | Apache-2.0 | D7 | Optimizing inference proxy for LLMs, a place to test decoding strategies. |
| 246 | OpenNMT/CTranslate2 | https://github.com/OpenNMT/CTranslate2 | 4713 | 2026-10-21 | C++ | MIT | D7 | Transformer inference engine, the local backend that LeanCopilot uses for models. |
| 247 | NVIDIA/Model-Optimizer | https://github.com/NVIDIA/Model-Optimizer | 5387 | 2026-10-21 | Python | Apache-2.0 | D7 | Quantization, distillation and pruning library for shrinking models before serving. |
| 248 | mistralai/mistral-inference | https://github.com/mistralai/mistral-inference | 10819 | 2026-10-20 | Jupyter Notebook | Apache-2.0 | D7 | Official inference library for Mistral models, a reference serving codebase. |
| 249 | flashinfer-ai/flashinfer | https://github.com/flashinfer-ai/flashinfer | 6728 | 2026-10-21 | Cuda | Apache-2.0 | D7 | Kernel library for LLM serving, the attention kernels behind fast decoding. |
| 250 | xorbitsai/inference | https://github.com/xorbitsai/inference | 9619 | 2026-10-21 | Python | Apache-2.0 | D7 | OpenAI-compatible serving framework for running open LLMs. |

## Top 25 to try first

- 2. ChuyueSun/Clover: MIT; closed-loop Dafny generation with consistency checks, a specification-stage design to copy.
- 3. namin/llm-verified-with-monte-carlo-tree-search: MIT; verifier-guided tree search, a model for a bounded number of repair calls.
- 6. sun-wendy/DafnyBench: Apache-2.0; Dafny benchmark that runs locally, a yardstick for the specification stage.
- 15. microsoft/NeuralInvariantRanker: MIT; ranks candidate loop invariants, a small filter for the specification stage.
- 24. Purewhite2019/rethinking_autoformalization: Apache-2.0; faithfulness metric for natural-language-to-Lean statements, a specification-quality check.
- 48. lean-dojo/LeanDojo: MIT; Python toolkit that extracts Lean data and drives proof search from code.
- 49. lean-dojo/ReProver: MIT; a small Python retrieval-augmented prover with released models, a baseline for Lean repair loops that suits one GPU.
- 50. lean-dojo/LeanCopilot: MIT; local tactic suggestions inside Lean through CTranslate2, a route to a local prover loop.
- 56. stanford-centaur/PyPantograph: Apache-2.0; Python API to Lean 4 for search and training loops.
- 57. leanprover-community/repl: Apache-2.0; small Lean REPL that returns errors and sorries, the feedback source for repair turns.
- 58. oOo0oOo/lean-lsp-mcp: MIT; Lean diagnostics as MCP tools, a verifier-feedback channel that needs no GPU.
- 60. project-numina/kimina-lean-server: MIT; batched Lean checking of candidate proofs, a verifier service for repair turns.
- 66. DebarghaG/proofofthought: MIT; Python pipeline where Z3 checks LLM reasoning, a verifier-in-the-loop design to copy.
- 82. epfl-lara/LeanProbe: MIT; Lean 4 proof feedback for coding agents through a Python library and an MCP server.
- 116. huggingface/trl: Apache-2.0; Python RL trainer with GRPO and custom reward functions.
- 128. unslothai/unsloth: Apache-2.0; single-GPU fine-tuning and RL training for local models.
- 144. policy-gradient/GRPO-Zero: Apache-2.0; GRPO written from scratch, the shortest path to a verifier-reward loop.
- 173. deepseek-ai/DeepSeek-Prover-V1.5: MIT repository for a Lean 4 prover model, a candidate for local inference experiments.
- 191. ggml-org/llama.cpp: MIT; GGUF serving with GBNF grammars, the runtime for a Q8 student.
- 192. abetlen/llama-cpp-python: MIT; Python bindings with grammar sampling for GGUF models on one GPU.
- 198. guidance-ai/llguidance: MIT; constrained-decoding grammar engine that llama.cpp can use for grammars.
- 199. dottxt-ai/outlines: Apache-2.0; Python structured generation for JSON schema and regex constraints.
- 200. mlc-ai/xgrammar: Apache-2.0; grammar-constrained decoding engine, the structured-output option for the route.
- 213. FasterDecoding/Medusa: Apache-2.0; Python multi-head decoding that speeds up generation from one model.
- 217. hao-ai-lab/LookaheadDecoding: Apache-2.0; Python decoding without a draft model, a single-GPU speed option.
