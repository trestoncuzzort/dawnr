# repos-B: public repositories for dawnr (D4, D5, D6, D8)

- Date (UTC): 2026-10-21
- Method: 259 gh search repos queries (188 in the first set, 71 in a second set with sort and language filters; 89 of the first set returned zero hits because GitHub ANDs multi-word terms); 12 WebSearch queries for named benchmarks and provers; 8 gh repo view confirmations of repositories named in those results (the nl-2-postcond link resolves to intent-formalization). Raw hits 12040 from 6839 unique repositories after dedupe by full name. Filtered by topic terms (dafny, verus, F*, SPARK, Frama-C, Lean, Rocq, invariant, termination, SMT, mutation, benchmark terms), then reviewed by hand; excluded Verus-coin cryptocurrency repos, Apache Spark, Houdini, hardware, neural-network verification and generic tools. Stars, dates, language and licence are copied from the stored gh output, not from memory.
- Issues: D4 datasets and data generation; D5 invariant and proof synthesis; D6 kernels, translation, harnesses and twin checks; D8 benchmarks and evaluation harnesses.
- Totals: 250 entries; D4 47, D5 59, D6 101, D8 47 (a row can carry two tags); star median 30; permissive-licence entries 158 (Apache-2.0, MIT, BSD, ISC, MPL-2.0 and 0BSD; CC0 and CC-BY not counted).

| # | repo | link | stars | last update | language | licence | issues | why it may help |
|---|---|---|---|---|---|---|---|---|
| 1 | sun-wendy/DafnyBench | https://github.com/sun-wendy/DafnyBench | 69 | 2026-10-13 | Dafny | Apache-2.0 | D8 | Dafny verification benchmark of real programs with specs, the main yardstick for the Dafny lane. |
| 2 | dafny-lang/dafny | https://github.com/dafny-lang/dafny | 3587 | 2026-10-19 | C# | NOASSERTION | D6 | Reference Dafny verifier and compiler; the batch kernel for Dafny runs and version pinning. |
| 3 | dafny-lang/miniF2F | https://github.com/dafny-lang/miniF2F | 11 | 2026-07-30 | Dafny | MIT | D8 | Dafny port of the miniF2F formal-to-formal math benchmark for proof-generation tests. |
| 4 | dafny-lang/libraries | https://github.com/dafny-lang/libraries | 49 | 2026-07-30 | Dafny | NOASSERTION | D4 | Shared Dafny library code usable as a verified corpus and as imports for generated programs. |
| 5 | dafny-lang/b3 | https://github.com/dafny-lang/b3 | 30 | 2026-10-05 | Dafny | MIT | D6 | Intermediate verification language from the Dafny team, a candidate lowering target beside Boogie. |
| 6 | dafny-lang/xdsmith | https://github.com/dafny-lang/xdsmith | 12 | 2026-07-30 | Racket | MIT | D6 | Fuzzer for the Dafny compiler, usable as a differential harness for kernel and twin checks. |
| 7 | dafny-lang/setup-dafny-action | https://github.com/dafny-lang/setup-dafny-action | 3 | 2025-09-02 | JavaScript | MIT | D6 | GitHub Action that pins and installs a Dafny version for reproducible batch verification. |
| 8 | dafny-lang/dafny-reportgenerator | https://github.com/dafny-lang/dafny-reportgenerator | 3 | 2022-08-26 | Dafny | MIT | D6 | Analyses and reports Dafny verification results, useful for timing and budget curves. |
| 9 | metareflection/dafny-replay | https://github.com/metareflection/dafny-replay | 41 | 2026-10-05 | TypeScript | MIT | D4 | Verified kernels written in Dafny and compiled to JavaScript, a worked corpus with replay tooling. |
| 10 | metareflection/dafny-replay-bench | https://github.com/metareflection/dafny-replay-bench | 2 | 2026-06-25 | Dafny | MIT | D8 | Dafny proof benchmark built from the dafny-replay corpus. |
| 11 | metareflection/dafny-annotator | https://github.com/metareflection/dafny-annotator | 21 | 2026-10-15 | Python | MIT | D5 | AI-assisted tool that adds Dafny annotations and proof hints to programs. |
| 12 | metareflection/dafny2js | https://github.com/metareflection/dafny2js | 3 | 2026-10-05 | C# | MIT | D6 | Streamlined Dafny-to-JavaScript compilation for generated verified code. |
| 13 | namin/dafny-mcp | https://github.com/namin/dafny-mcp | 3 | 2026-04-24 | Python | MIT | D6 | MCP server that exposes the Dafny verifier to agents, a harness for batch verification calls. |
| 14 | namin/dafny-sketcher | https://github.com/namin/dafny-sketcher | 18 | 2026-07-31 | Dafny | MIT | D5 | Explores interactive semi-automated verified program synthesis on the Dafny implementation. |
| 15 | ggrov/tacny | https://github.com/ggrov/tacny | 3 | 2026-06-26 | C# | unknown | D5 | Tactic language for the Dafny verifier, a proof-search aid for Dafny lemmas and assertions. |
| 16 | arsalan0c/dafny-of-python | https://github.com/arsalan0c/dafny-of-python | 36 | 2026-10-18 | OCaml | unknown | D6 | Deductive verification of Python programs by translation to Dafny, a Python-to-spec lowering path. |
| 17 | JetBrains-Research/HumanEval-Dafny | https://github.com/JetBrains-Research/HumanEval-Dafny | 12 | 2026-07-02 | Dafny | Apache-2.0 | D8 | HumanEval problems translated into Dafny with specifications, an MBPP-style verification set. |
| 18 | Beneficial-AI-Foundation/vericoding-dafny-benchmark | https://github.com/Beneficial-AI-Foundation/vericoding-dafny-benchmark | 0 | 2025-09-02 | Dafny | MIT | D8 | Dafny task set from the vericoding benchmark family (description empty, name-based). |
| 19 | Beneficial-AI-Foundation/vericoded-dafny-benchmark | https://github.com/Beneficial-AI-Foundation/vericoded-dafny-benchmark | 0 | 2025-10-20 | Dafny | MIT | D8 | Second Dafny task set from the vericoding family for cross-checking benchmark numbers (description empty, name-based). |
| 20 | Beneficial-AI-Foundation/dafny-autopilot | https://github.com/Beneficial-AI-Foundation/dafny-autopilot | 15 | 2026-10-11 | TypeScript | MIT | D5 | Automated proof assistance for Dafny programs (description empty, name-based). |
| 21 | midspiral/lemmascript-dafny-benchmark | https://github.com/midspiral/lemmascript-dafny-benchmark | 0 | 2026-09-27 | Dafny | NOASSERTION | D8 | Dafny benchmark extracted from LemmaScript case studies for proof-completion evaluation. |
| 22 | midspiral/LemmaScript | https://github.com/midspiral/LemmaScript | 120 | 2026-10-19 | TypeScript | MIT | D4 | Verification toolchain that turns annotated TypeScript into checked proofs, a source of verified program pairs. |
| 23 | crishN144/dafny-eval | https://github.com/crishN144/dafny-eval | 0 | 2026-08-17 | Python | unknown | D8 | Soundness-hardened benchmark for LLM Dafny invariant synthesis. |
| 24 | NVictor2004/dafny-equivalence-benchmarks | https://github.com/NVictor2004/dafny-equivalence-benchmarks | 0 | 2026-06-08 | Dafny | Apache-2.0 | D8 | Dataset of equivalent and non-equivalent Dafny functions for equivalence benchmarks. |
| 25 | NVictor2004/equidafny | https://github.com/NVictor2004/equidafny | 0 | 2026-08-28 | HTML | Apache-2.0 | D6 | Equivalence checker for Dafny functions, a twin-style check that programs match their specs. |
| 26 | revathi-prasad/spec-laundering | https://github.com/revathi-prasad/spec-laundering | 0 | 2026-05-25 | Python | unknown | D6 | Spec-laundering attacks against Dafny verification with a benchmark and detector, relevant to vacuity checks. |
| 27 | SystemicVoid/secure-synth-hackathon | https://github.com/SystemicVoid/secure-synth-hackathon | 0 | 2026-05-24 | Python | unknown | D8 | SpecFault-Dafny benchmark and validator package for secure program synthesis. |
| 28 | Consensys-Incorporated/evm-dafny | https://github.com/Consensys-Incorporated/evm-dafny | 141 | 2026-10-11 | Dafny | Apache-2.0 | D4 | EVM interpreter verified in Dafny, a larger verified-program corpus. |
| 29 | Consensys-inc-archive/eth2.0-dafny | https://github.com/Consensys-inc-archive/eth2.0-dafny | 80 | 2026-09-25 | Dafny | Apache-2.0 | D4 | Eth2.0 specification written in Dafny, a verified corpus of protocol code. |
| 30 | mit-pdos/daisy-nfsd | https://github.com/mit-pdos/daisy-nfsd | 43 | 2026-10-07 | Dafny | MIT | D4 | NFS server verified with Dafny and Perennial, a systems-scale verified corpus. |
| 31 | Consensys/DafnyCrypto | https://github.com/Consensys/DafnyCrypto | 4 | 2025-02-15 | Dafny | Apache-2.0 | D4 | Cryptography library in Dafny focused on SNARK components, a verified corpus. |
| 32 | jonhnet/tla-dafny | https://github.com/jonhnet/tla-dafny | 6 | 2024-04-27 | unknown | Apache-2.0 | D6 | Embedding of TLA+ in Dafny, an example of translating between verification languages. |
| 33 | Nangos/verified-algorithms | https://github.com/Nangos/verified-algorithms | 5 | 2025-04-25 | Dafny | unknown | D4 | Verified algorithms written with Dafny tools, a small corpus of verified programs. |
| 34 | yanliang1439/verified-sql-engine | https://github.com/yanliang1439/verified-sql-engine | 1 | 2026-10-01 | Dafny | unknown | D4 | Formally verified SQL query engine in Dafny covering WHERE, SELECT and ORDER BY. |
| 35 | DavisPL/PCCC | https://github.com/DavisPL/PCCC | 11 | 2026-01-12 | C# | NOASSERTION | D5 | Proof-carrying code completions in Dafny, a route to completions that come with checked proofs. |
| 36 | melek/proven | https://github.com/melek/proven | 0 | 2026-03-28 | Python | MIT | D5 | LLM-driven stepwise refinement with Dafny verification from requirements to verified code. |
| 37 | DimitriosThomaidis/AutoProv | https://github.com/DimitriosThomaidis/AutoProv | 1 | 2026-06-30 | Python | MIT | D5 | CI/CD pipeline that uses LLMs and SMT solvers, including Dafny, to produce verified code. |
| 38 | rupnikj/dafny-verify-browser | https://github.com/rupnikj/dafny-verify-browser | 1 | 2026-08-26 | JavaScript | MIT | D6 | Runs Dafny 4.11 and Boogie entirely in the browser, a light harness for verification calls. |
| 39 | Gy-Hu/VC2SMT-research | https://github.com/Gy-Hu/VC2SMT-research | 0 | 2026-06-02 | Shell | unknown | D6 | Study of how Dafny, Frama-C/WP and other verifiers turn verification conditions into SMT-LIB. |
| 40 | Wannavf/Certum | https://github.com/Wannavf/Certum | 1 | 2026-05-10 | unknown | unknown | D6 | Verification compiler that lowers C, Rust, Go and Solidity to Dafny, Z3, Lean, Coq, F* and ACSL. |
| 41 | vectorpikachu/Transpiler-from-C-to-Dafny | https://github.com/vectorpikachu/Transpiler-from-C-to-Dafny | 1 | 2025-06-20 | Rust | MIT | D6 | Simple transpiler from C to Dafny, a lowering example for translation between verifiers. |
| 42 | chthonic7/solidity-to-dafny | https://github.com/chthonic7/solidity-to-dafny | 1 | 2022-04-08 | unknown | unknown | D6 | Translation of Solidity contracts to Dafny for verification. |
| 43 | YiLai-qed/DafFuzz | https://github.com/YiLai-qed/DafFuzz | 0 | 2023-06-12 | Dafny | unknown | D6 | Metamorphic fuzzer for the Dafny verifier, a test harness for verifier bugs. |
| 44 | YiLai-qed/dafl-sharp | https://github.com/YiLai-qed/dafl-sharp | 0 | 2023-04-01 | C# | MIT | D6 | Metamorphic fuzzing tool for the Dafny verifier, a second harness for verifier testing. |
| 45 | fuzz-d/fuzz-d | https://github.com/fuzz-d/fuzz-d | 7 | 2026-07-28 | Kotlin | MIT | D6 | Random program generator that fuzzes the Dafny compiler, a source of stress programs. |
| 46 | CompFuzzCI/DafnyCompilerFuzzer | https://github.com/CompFuzzCI/DafnyCompilerFuzzer | 2 | 2025-06-15 | Python | unknown | D6 | Fuzzer for the Dafny compiler, a stress harness for the Dafny kernel (description empty, name-based). |
| 47 | agawde05/rlvr-dafnybench | https://github.com/agawde05/rlvr-dafnybench | 0 | 2026-08-23 | Python | unknown | D8 | RL training with verifiable rewards on DafnyBench (description empty, name-based). |
| 48 | verus-lang/verus | https://github.com/verus-lang/verus | 3364 | 2026-10-21 | Rust | MIT | D6 | Verus SMT-based verifier for Rust, the kernel for the Verus lane. |
| 49 | microsoft/verus-proof-synthesis | https://github.com/microsoft/verus-proof-synthesis | 123 | 2026-10-20 | Rust | MIT | D5 | Verus proof synthesis code and benchmark set, the AutoVerus line of work (description empty, name-based). |
| 50 | microsoft/verus-copilot-vscode | https://github.com/microsoft/verus-copilot-vscode | 18 | 2026-10-10 | Rust | MIT | D5 | LLM copilot for writing Verus proofs inside VS Code (description empty, name-based). |
| 51 | secure-foundations/human-eval-verus | https://github.com/secure-foundations/human-eval-verus | 29 | 2026-09-26 | Rust | MIT | D8 | HumanEval problems rewritten as Verus tasks, a direct MBPP-style verification yardstick (description empty, name-based). |
| 52 | HIPREL-Group/VeriContest | https://github.com/HIPREL-Group/VeriContest | 14 | 2026-10-21 | Rust | Apache-2.0 | D8 | Large-scale competitive-programming verification benchmark in Verus, a close match to the panel task shape. |
| 53 | verus-lang/verus-spec-check | https://github.com/verus-lang/verus-spec-check | 12 | 2026-10-20 | Rust | MIT | D6 | Tools that test soundness and completeness of Verus specifications, close to twin and vacuity checks. |
| 54 | e-p-armstrong/verustoolkit | https://github.com/e-p-armstrong/verustoolkit | 11 | 2025-03-20 | Python | MIT | D4 | Augmentoolkit-style synthetic data generation for Verus, a data-generation pipeline to study. |
| 55 | matthias-brun/verus-find | https://github.com/matthias-brun/verus-find | 10 | 2026-10-11 | Rust | MIT | D5 | Search tool for Verus functions and lemmas, a premise-retrieval aid for Verus proofs. |
| 56 | parno/verus-ai | https://github.com/parno/verus-ai | 7 | 2026-10-03 | unknown | MIT | D5 | AI tools for Verus, a small collection of proof-assistance utilities. |
| 57 | verus-lang/verified-ironkv | https://github.com/verus-lang/verified-ironkv | 12 | 2026-10-11 | Rust | MIT | D4 | Verus-verified sharded hash table from the Ironfleet line, a large verified Rust corpus. |
| 58 | verus-lang/verified-memory-allocator | https://github.com/verus-lang/verified-memory-allocator | 38 | 2026-10-09 | Rust | NOASSERTION | D4 | Memory allocator verified with Verus, a systems-level verified corpus. |
| 59 | secure-foundations/vest | https://github.com/secure-foundations/vest | 102 | 2026-10-18 | Rust | MIT | D4 | Verified Rust parsing and serialization written with Verus, a corpus of verified parsers. |
| 60 | ilyasergey/vermilion | https://github.com/ilyasergey/vermilion | 61 | 2026-10-20 | Lean | Apache-2.0 | D6 | Verus meets Lean, a bridge that moves Verus-style specifications toward Lean proofs. |
| 61 | anvil-verifier/verus-tla | https://github.com/anvil-verifier/verus-tla | 29 | 2026-10-16 | Rust | MIT | D6 | TLA embedding in Verus, a translation between a spec language and a Verus kernel. |
| 62 | verus-lang/verusfmt | https://github.com/verus-lang/verusfmt | 22 | 2026-10-16 | Rust | MIT | D6 | Opinionated formatter for Verus code, a tidy step for generated Verus files. |
| 63 | briangmilnes/APAS-VERUS | https://github.com/briangmilnes/APAS-VERUS | 10 | 2026-09-25 | Rust | MIT | D4 | Proofs of parallel and sequential algorithms in Verus, a verified algorithm corpus. |
| 64 | rikosellic/verus-mathspec-bench | https://github.com/rikosellic/verus-mathspec-bench | 0 | 2026-05-23 | Rust | Apache-2.0 | D8 | Verus benchmark for pure mathematical theories, a verified-math yardstick. |
| 65 | amarshah1/verus-benchmarks | https://github.com/amarshah1/verus-benchmarks | 0 | 2026-05-07 | SMT | unknown | D8 | Collection of Verus benchmark programs (description empty, name-based). |
| 66 | amarshah1/verus_benchmarks | https://github.com/amarshah1/verus_benchmarks | 0 | 2026-10-06 | SMT | unknown | D8 | Second Verus benchmark collection under a different name (description empty, name-based). |
| 67 | Beneficial-AI-Foundation/vericoding-verus-benchmark | https://github.com/Beneficial-AI-Foundation/vericoding-verus-benchmark | 0 | 2025-09-05 | Rust | MIT | D8 | Verus task set from the vericoding benchmark family (description empty, name-based). |
| 68 | Beneficial-AI-Foundation/vericoded-verus-benchmark | https://github.com/Beneficial-AI-Foundation/vericoded-verus-benchmark | 0 | 2025-10-20 | Rust | MIT | D8 | Second Verus task set from the vericoding family for cross-checking numbers (description empty, name-based). |
| 69 | sarsko/CreuSAT | https://github.com/sarsko/CreuSAT | 704 | 2026-10-19 | Rust | MIT | D4 | Formally verified SAT solver in Rust with Creusot, a verified program corpus. |
| 70 | cryspen/hax | https://github.com/cryspen/hax | 488 | 2026-10-20 | Rust | Apache-2.0 | D6 | Rust verification tool that translates Rust into proof-assistant backends such as F*. |
| 71 | AeneasVerif/aeneas | https://github.com/AeneasVerif/aeneas | 1075 | 2026-10-20 | OCaml | Apache-2.0 | D6 | Verification toolchain that translates Rust into proof-assistant models such as Lean. |
| 72 | AeneasVerif/charon | https://github.com/AeneasVerif/charon | 448 | 2026-10-20 | Rust | Apache-2.0 | D6 | Rust analysis frontend that feeds Aeneas, a stage in the Rust-to-prover pipeline. |
| 73 | creusot-rs/creusot | https://github.com/creusot-rs/creusot | 1931 | 2026-10-21 | Rust | LGPL-2.1 | D6 | Deductive Rust verifier that proves Rust code with Why3 back ends. |
| 74 | prusti/prusti | https://github.com/prusti/prusti | 1820 | 2026-10-20 | Rust | NOASSERTION | D6 | Static Rust verifier built on Viper, a second Rust kernel for comparison. |
| 75 | secure-foundations/tree-sitter-verus | https://github.com/secure-foundations/tree-sitter-verus | 13 | 2026-09-12 | JavaScript | MIT | D6 | Tree-sitter grammar for Verus, a parser for AST-level edits and mutation (description empty, name-based). |
| 76 | JakeGinesin/verus-flake | https://github.com/JakeGinesin/verus-flake | 4 | 2026-10-05 | Nix | unknown | D6 | Nix flake that pins a Verus toolchain, an example of prover version pinning. |
| 77 | pulseengine/gale | https://github.com/pulseengine/gale | 6 | 2026-10-15 | Rust | Apache-2.0 | D4 | Rust port of Zephyr kernel primitives verified with Verus and Rocq, a dual-track verified corpus. |
| 78 | Je5s1e/KDD26-ADS-StarVerus | https://github.com/Je5s1e/KDD26-ADS-StarVerus | 6 | 2026-10-20 | Rust | MIT | D5 | LLM multi-agent system for industrial Rust verification automation, an agentic proof pipeline. |
| 79 | FStarLang/FStar | https://github.com/FStarLang/FStar | 3121 | 2026-10-21 | F* | Apache-2.0 | D6 | F* proof-oriented language and verifier, one of the seven kernels in the lowering target. |
| 80 | hacl-star/hacl-star | https://github.com/hacl-star/hacl-star | 1842 | 2026-10-19 | F* | Apache-2.0 | D4 | HACL*, a formally verified cryptographic library in F*, a large verified corpus. |
| 81 | project-everest/ethereum-star | https://github.com/project-everest/ethereum-star | 9 | 2026-07-02 | Solidity | Apache-2.0 | D4 | F* proofs of Ethereum components, a verified-program corpus in F*. |
| 82 | project-everest/mitls-fstar | https://github.com/project-everest/mitls-fstar | 183 | 2026-09-03 | F* | NOASSERTION | D4 | Verified TLS 1.3 implementation in F*, a larger verified protocol corpus. |
| 83 | TakuKitamura/verimqtt | https://github.com/TakuKitamura/verimqtt | 1 | 2021-03-29 | F* | Apache-2.0 | D4 | Formally verified MQTT library written in F*, a small verified corpus. |
| 84 | mssabr01/ICSVerifiedSoftwareProject | https://github.com/mssabr01/ICSVerifiedSoftwareProject | 5 | 2026-04-12 | C | unknown | D4 | Verified bolt-on security device for ICS networks written and proved in F*, a corpus example. |
| 85 | nikicat/verified-ledger | https://github.com/nikicat/verified-ledger | 0 | 2026-08-05 | Lean | Apache-2.0 | D4 | Rust token ledger with machine-checked money conservation using hax, F* and Z3. |
| 86 | artagnon/vsfstar | https://github.com/artagnon/vsfstar | 16 | 2025-11-13 | TypeScript | MIT | D6 | VS Code extension for F* with IDE features, an editor harness for F* files. |
| 87 | kant2002/FStarMSBuildSdk | https://github.com/kant2002/FStarMSBuildSdk | 8 | 2026-08-25 | F* | MIT | D6 | MSBuild SDK for F*, a build harness for batch F* verification. |
| 88 | sei40kr/tree-sitter-fstar | https://github.com/sei40kr/tree-sitter-fstar | 0 | 2026-03-14 | C | MIT | D6 | Tree-sitter grammar for F*, a parser for AST-level tooling. |
| 89 | smheidrich/fstar-vsca-lsp-server | https://github.com/smheidrich/fstar-vsca-lsp-server | 0 | 2026-07-05 | Shell | unknown | D6 | Language server extracted from the F* VS Code assistant, a harness for F* checking. |
| 90 | Smfakhoury/fstar-user-study | https://github.com/Smfakhoury/fstar-user-study | 0 | 2026-02-26 | Python | unknown | D5 | F* proof agent with a spec-first planner strategy from a user study, a proof-search design. |
| 91 | AdaCore/spark2014 | https://github.com/AdaCore/spark2014 | 330 | 2026-10-20 | Ada | GPL-3.0 | D6 | SPARK 2014 toolset with GNATprove, one of the seven kernels in the lowering target. |
| 92 | AdaCore/why3 | https://github.com/AdaCore/why3 | 40 | 2026-10-15 | OCaml | NOASSERTION | D6 | Why3 verification platform, the backend behind GNATprove and Frama-C WP. |
| 93 | tofgarion/spark-by-example | https://github.com/tofgarion/spark-by-example | 167 | 2026-08-22 | Ada | unknown | D8 | SPARK by Example, a tutorial set of SPARK programs usable as small verification tasks. |
| 94 | fraunhoferfokus/acsl-by-example | https://github.com/fraunhoferfokus/acsl-by-example | 128 | 2026-10-15 | Rocq Prover | MIT | D4 | Snapshots of ACSL by Example, a set of annotated C programs for Frama-C tasks. |
| 95 | evdenis/acsl-examples | https://github.com/evdenis/acsl-examples | 7 | 2025-03-18 | C | MIT | D4 | Tiny C programs with ACSL specifications, a small corpus for Frama-C tests. |
| 96 | evdenis/acsl-proved | https://github.com/evdenis/acsl-proved | 17 | 2025-12-26 | C | unknown | D4 | Fully proved small C functions with ACSL, a worked corpus of verified C. |
| 97 | evdenis/spec-utils | https://github.com/evdenis/spec-utils | 11 | 2026-09-01 | Perl | GPL-2.0 | D5 | Utilities for writing ACSL specifications, a helper set for specification drafting. |
| 98 | rse-verification/saida | https://github.com/rse-verification/saida | 5 | 2026-10-09 | C | GPL-2.0 | D5 | Frama-C plugin that infers ACSL contracts for C helper functions, a specification-inference route. |
| 99 | Frama-C/Frama-C-snapshot | https://github.com/Frama-C/Frama-C-snapshot | 190 | 2026-10-02 | OCaml | unknown | D6 | Release snapshots of the Frama-C platform, the C kernel used with ACSL and WP. |
| 100 | Frama-C/open-source-case-studies | https://github.com/Frama-C/open-source-case-studies | 35 | 2026-07-02 | C | unknown | D4 | Open-source case studies for Frama-C, mainly EVA value analysis, a real-code corpus. |
| 101 | Frama-C/github-action-eva-sarif | https://github.com/Frama-C/github-action-eva-sarif | 11 | 2026-10-04 | Shell | unknown | D6 | GitHub Action that runs the Frama-C EVA plug-in and emits SARIF, a CI harness. |
| 102 | Frama-C/SATE-VI | https://github.com/Frama-C/SATE-VI | 9 | 2026-07-02 | Shell | unknown | D8 | Reproduction of NIST SATE VI results with Frama-C EVA on the Juliet suite, a benchmark reproduction. |
| 103 | sysprog21/frama-c-mcp | https://github.com/sysprog21/frama-c-mcp | 35 | 2026-10-16 | Rust | MIT | D6 | MCP server that gives agents Frama-C with EVA, WP and a sandbox, a harness for tool calls. |
| 104 | lihaokun/frama-c-mcp-server | https://github.com/lihaokun/frama-c-mcp-server | 2 | 2026-07-17 | Rust | MIT | D6 | MCP server for Frama-C that lets AI agents drive the platform, a second harness option. |
| 105 | gpetiot/Frama-C-Mutation | https://github.com/gpetiot/Frama-C-Mutation | 20 | 2025-04-06 | OCaml | unknown | D6 | Generation of mutant C programs with Frama-C, a mutation tool for twin construction. |
| 106 | gpetiot/Frama-C-StaDy | https://github.com/gpetiot/Frama-C-StaDy | 8 | 2026-01-05 | OCaml | LGPL-3.0 | D5 | Static and dynamic verification of C programs in Frama-C, a mixed analysis route. |
| 107 | ThalesGroup/frama-c-lsp | https://github.com/ThalesGroup/frama-c-lsp | 8 | 2026-10-14 | OCaml | LGPL-3.0 | D6 | Language server and client for Frama-C, an editor and automation harness. |
| 108 | schrodibear/astraver | https://github.com/schrodibear/astraver | 6 | 2026-07-11 | OCaml | NOASSERTION | D6 | Deductive verification tool for Linux kernel code built on Frama-C. |
| 109 | lihaokun/FermatVerification-bench | https://github.com/lihaokun/FermatVerification-bench | 0 | 2026-05-14 | C | NOASSERTION | D8 | Unified C plus ACSL verification benchmark for Frama-C and WP. |
| 110 | Beatgodes/klibc_framac_wp | https://github.com/Beatgodes/klibc_framac_wp | 11 | 2025-12-26 | C | unknown | D4 | klibc verified with Frama-C and WP, a real-library verified corpus. |
| 111 | AllanBlanchard/tutoriel_wp | https://github.com/AllanBlanchard/tutoriel_wp | 83 | 2026-09-21 | TeX | NOASSERTION | D4 | Frama-C and WP tutorial with worked verified examples. |
| 112 | pepega007xd/seal | https://github.com/pepega007xd/seal | 6 | 2026-10-14 | Typst | MIT | D5 | Frama-C plugin for shape analysis with separation logic, an invariant-style analysis. |
| 113 | HeisenbugLtd/spat | https://github.com/HeisenbugLtd/spat | 18 | 2026-10-10 | Ada | WTFPL | D6 | SPARK Proof Analysis Tool, a report and triage harness for GNATprove output. |
| 114 | mbeckersys/gnatprove_unitstats | https://github.com/mbeckersys/gnatprove_unitstats | 4 | 2025-07-07 | Python | MIT | D6 | Script that produces per-unit statistics from GNATprove runs, a budget and timing report. |
| 115 | damaki/gnatprove2xls | https://github.com/damaki/gnatprove2xls | 5 | 2025-11-03 | Python | unknown | D6 | Converts GNATprove report files to spreadsheets, a reporting helper for SPARK runs. |
| 116 | yoogx/spark_examples | https://github.com/yoogx/spark_examples | 9 | 2025-11-03 | Ada | unknown | D4 | Examples of SPARK2014 code, a small verified-program corpus (licence not stated). |
| 117 | mgrojo/coap_spark | https://github.com/mgrojo/coap_spark | 9 | 2026-09-30 | Ada | GPL-2.0 | D4 | Formally verified CoAP protocol implementation in SPARK, a verified-protocol corpus. |
| 118 | cubesatlab/cubedos | https://github.com/cubesatlab/cubedos | 63 | 2026-08-09 | Ada | unknown | D4 | Flight software framework written in SPARK/Ada, a larger verified systems corpus. |
| 119 | damaki/libkeccak | https://github.com/damaki/libkeccak | 40 | 2026-06-14 | Ada | BSD-3-Clause | D4 | SHA-3 and Keccak algorithms in SPARK/Ada, a verified cryptographic corpus. |
| 120 | RobertBoettcherSF/Ada-SPARK-Evaluate-Division-Lite | https://github.com/RobertBoettcherSF/Ada-SPARK-Evaluate-Division-Lite | 0 | 2026-09-24 | Ada | MIT | D4 | Bounded SPARK algorithm with a cvc5-checked level 2 proof, a verified example that uses an SMT back end. |
| 121 | lengyijun/tarjan-kosaraju-why3-lean4 | https://github.com/lengyijun/tarjan-kosaraju-why3-lean4 | 4 | 2025-01-17 | Lean | unknown | D6 | Tarjan and Kosaraju algorithms verified with Why3 and Lean 4, a cross-prover example (description empty, name-based). |
| 122 | xqyww123/why3-for-NTP | https://github.com/xqyww123/why3-for-NTP | 0 | 2025-08-29 | OCaml | NOASSERTION | D6 | Modified Why3 that exports verification conditions to Isabelle, Lean and Coq for neural theorem proving. |
| 123 | bladeacer/adacovex | https://github.com/bladeacer/adacovex | 11 | 2026-10-20 | Ada | Apache-2.0 | D6 | Ada and SPARK verification and compliance toolchain, a harness for SPARK proof runs. |
| 124 | jgrivera67/HiRTOS | https://github.com/jgrivera67/HiRTOS | 56 | 2026-10-13 | Ada | Apache-2.0 | D4 | High-integrity multi-core RTOS and separation kernel written in SPARK Ada, a verified systems corpus. |
| 125 | HeisenbugLtd/Saatana | https://github.com/HeisenbugLtd/Saatana | 16 | 2026-07-24 | Ada | WTFPL | D4 | Cryptographic framework proven correct in SPARK, a verified library corpus. |
| 126 | leanprover/lean4 | https://github.com/leanprover/lean4 | 9612 | 2026-10-21 | Lean | Apache-2.0 | D6 | Lean 4 language, elaborator and kernel, the proof checker behind every Lean lane. |
| 127 | leanprover/elan | https://github.com/leanprover/elan | 658 | 2026-10-17 | Rust | Apache-2.0 | D6 | Lean version manager, used to pin toolchains for reproducible prover runs. |
| 128 | digama0/lean4lean | https://github.com/digama0/lean4lean | 265 | 2026-10-19 | Lean | Apache-2.0 | D6 | External Lean 4 kernel checker, a second implementation for cross-checking proofs. |
| 129 | ammkrn/nanoda_lib | https://github.com/ammkrn/nanoda_lib | 215 | 2026-10-19 | Rust | Apache-2.0 | D6 | Lean type-checking library in Rust, another independent kernel for cross-checks. |
| 130 | intgrah/sokonanoda | https://github.com/intgrah/sokonanoda | 17 | 2026-10-13 | Rust | Apache-2.0 | D6 | Lean 4 kernel using normalization by evaluation, a further independent checker. |
| 131 | gebner/trepplein | https://github.com/gebner/trepplein | 42 | 2026-05-17 | Scala | Apache-2.0 | D6 | Lean type checker written in Scala, an independent checker for cross-checking. |
| 132 | stanford-centaur/PyPantograph | https://github.com/stanford-centaur/PyPantograph | 150 | 2026-10-20 | Python | Apache-2.0 | D6 | Machine-to-machine interface to Lean 4 for search and training loops. |
| 133 | augustepoiroux/LeanInteract | https://github.com/augustepoiroux/LeanInteract | 133 | 2026-10-20 | Python | MIT | D6 | Python interface to Lean 4 for scripted proof checking and interaction. |
| 134 | oOo0oOo/lean-lsp-mcp | https://github.com/oOo0oOo/lean-lsp-mcp | 531 | 2026-10-20 | Python | MIT | D6 | MCP server for Lean, letting agents call the Lean language server. |
| 135 | project-numina/kimina-lean-server | https://github.com/project-numina/kimina-lean-server | 212 | 2026-09-30 | Python | MIT | D6 | High-throughput Lean REPL server for verification at training scale. |
| 136 | ufmg-smite/lean-smt | https://github.com/ufmg-smite/lean-smt | 314 | 2026-10-20 | Lean | Apache-2.0 | D6 | Tactics that send Lean goals to SMT solvers, a bridge from Lean to Z3 and cvc5. |
| 137 | abdoo8080/lean-cvc5 | https://github.com/abdoo8080/lean-cvc5 | 26 | 2026-09-27 | Lean | Apache-2.0 | D6 | Foreign function interface from Lean to cvc5, a direct solver route inside Lean. |
| 138 | lenianiva/lean4-nix | https://github.com/lenianiva/lean4-nix | 126 | 2026-10-20 | Nix | Apache-2.0 | D6 | Nix overlay for Lean 4 and lake builds, a reproducible toolchain pin. |
| 139 | reilabs/lampe | https://github.com/reilabs/lampe | 43 | 2026-10-14 | Lean | Apache-2.0 | D6 | Extracts Noir circuit semantics into Lean for end-to-end verification, a translation route. |
| 140 | leanprover-community/mathlib4 | https://github.com/leanprover-community/mathlib4 | 4331 | 2026-10-21 | Lean | Apache-2.0 | D4 | Mathlib, the main Lean library and the corpus used for premise selection and autoformalization. |
| 141 | facebookresearch/atlas-lean | https://github.com/facebookresearch/atlas-lean | 312 | 2026-10-21 | Lean | NOASSERTION | D4 | ATLAS autoformalized textbook library in Lean, a large autoformalization corpus. |
| 142 | ProofOfKeags/btc-verified | https://github.com/ProofOfKeags/btc-verified | 27 | 2026-10-20 | Lean | Apache-2.0 | D4 | Verified Bitcoin protocol components in Lean 4, a verified-program corpus. |
| 143 | stepfun-ai/StepFun-Formalizer | https://github.com/stepfun-ai/StepFun-Formalizer | 29 | 2026-06-30 | Python | Apache-2.0 | D4 | Autoformalization model and data work for turning informal math into Lean. |
| 144 | THUNLP-MT/FormaRL | https://github.com/THUNLP-MT/FormaRL | 14 | 2026-07-15 | Python | MIT | D4 | Autoformalization without labeled data, a synthetic-data route to formal statements. |
| 145 | JOSHCLUNE/LeanHammer | https://github.com/JOSHCLUNE/LeanHammer | 101 | 2026-10-15 | Lean | Apache-2.0 | D5 | Automated reasoning hammer for Lean that combines premise selection with solver calls. |
| 146 | hanwenzhu/LeanHammer-training | https://github.com/hanwenzhu/LeanHammer-training | 8 | 2026-09-24 | Python | Apache-2.0 | D4 | Premise selection training and evaluation for LeanHammer, a data and training route. |
| 147 | leanprover-community/duper | https://github.com/leanprover-community/duper | 118 | 2026-10-01 | Lean | Apache-2.0 | D5 | Superposition prover for Lean goals, an automated proof-search back end (description empty, name-based). |
| 148 | leanprover-community/aesop | https://github.com/leanprover-community/aesop | 409 | 2026-10-19 | Lean | Apache-2.0 | D5 | White-box proof search automation for Lean 4, a tactic framework for proof search. |
| 149 | chasenorman/CanonicalLean | https://github.com/chasenorman/CanonicalLean | 139 | 2026-10-12 | Lean | MIT | D5 | Lean tactic built on Canonical, a sound and complete term search procedure. |
| 150 | nomeata/loogle | https://github.com/nomeata/loogle | 157 | 2026-10-16 | Lean | Apache-2.0 | D5 | Search tool for Mathlib lemmas, a premise-retrieval aid. |
| 151 | lean-explore/lean-explore | https://github.com/lean-explore/lean-explore | 82 | 2026-10-19 | Python | Apache-2.0 | D5 | Search engine over Lean declarations, a premise-search index. |
| 152 | BartoszPiotrowski/lean-premise-selection | https://github.com/BartoszPiotrowski/lean-premise-selection | 23 | 2026-08-08 | Lean | unknown | D5 | Premise selection for Lean, a retrieval route for proof search (description empty, name-based). |
| 153 | lean-dojo/LeanCopilot | https://github.com/lean-dojo/LeanCopilot | 1335 | 2026-10-19 | C++ | MIT | D5 | LLMs as copilots for Lean proving, a tactic-suggestion baseline. |
| 154 | lean-dojo/ReProver | https://github.com/lean-dojo/ReProver | 339 | 2026-10-13 | Python | MIT | D5 | Retrieval-augmented theorem provers for Lean, a premise-selection and prover baseline. |
| 155 | lean-dojo/LeanDojo | https://github.com/lean-dojo/LeanDojo | 848 | 2026-10-20 | Python | MIT | D4 | Data extraction and interaction tool for Lean programs, a route to Lean training data. |
| 156 | lean-dojo/LeanDojo-v2 | https://github.com/lean-dojo/LeanDojo-v2 | 147 | 2026-10-16 | Python | Apache-2.0 | D5 | End-to-end framework for training and evaluating Lean provers. |
| 157 | lean-dojo/LeanAgent | https://github.com/lean-dojo/LeanAgent | 88 | 2026-10-20 | Python | unknown | D5 | Lifelong learning framework for formal proving in Lean. |
| 158 | wellecks/llmstep | https://github.com/wellecks/llmstep | 155 | 2026-09-16 | Python | MIT | D5 | LLM proof-step suggestions in Lean 4, a tactic-level assistant. |
| 159 | verse-lab/velvet | https://github.com/verse-lab/velvet | 131 | 2026-10-17 | Lean | Apache-2.0 | D5 | Auto-active program verifier in Lean, a spec and invariant route inside Lean. |
| 160 | google-deepmind/formal-conjectures | https://github.com/google-deepmind/formal-conjectures | 1331 | 2026-10-20 | Lean | Apache-2.0 | D8 | Formalized statements of open and known conjectures in Lean, a benchmark source. |
| 161 | dwrensha/compfiles | https://github.com/dwrensha/compfiles | 256 | 2026-10-13 | Lean | Apache-2.0 | D8 | Catalog of competition math problems formalized in Lean, a Lean benchmark set. |
| 162 | zhangir-azerbayev/ProofNet | https://github.com/zhangir-azerbayev/ProofNet | 128 | 2026-10-20 | Lean | MIT | D8 | ProofNet benchmark of undergraduate formal mathematics. |
| 163 | rahul3613/ProofNet-lean4 | https://github.com/rahul3613/ProofNet-lean4 | 31 | 2026-10-20 | TeX | MIT | D8 | ProofNet ported to Lean 4 for autoformalization and proving tests. |
| 164 | marcusm117/ProofNet-Verified | https://github.com/marcusm117/ProofNet-Verified | 3 | 2026-10-20 | Lean | Apache-2.0 | D8 | Audited and corrected ProofNet, a cleaner variant for evaluation. |
| 165 | facebookresearch/miniF2F | https://github.com/facebookresearch/miniF2F | 108 | 2026-10-20 | Objective-C++ | MIT | D8 | Updated miniF2F with fixes, a standard formal olympiad benchmark. |
| 166 | yangky11/miniF2F-lean4 | https://github.com/yangky11/miniF2F-lean4 | 75 | 2026-07-21 | Lean | MIT | D8 | miniF2F ported to Lean 4, a Lean yardstick for proof search (description empty, name-based). |
| 167 | google-deepmind/miniF2F | https://github.com/google-deepmind/miniF2F | 15 | 2026-10-08 | Lean | Apache-2.0 | D8 | Lean 4 fork of miniF2F with corrections, a second Lean port for comparison. |
| 168 | rahul3613/miniF2F-lean4 | https://github.com/rahul3613/miniF2F-lean4 | 7 | 2025-12-16 | Lean | MIT | D8 | miniF2F dataset in Lean 4, a further port for evaluation. |
| 169 | openai/miniF2F | https://github.com/openai/miniF2F | 438 | 2026-10-15 | Objective-C++ | unknown | D8 | Original formal-to-formal olympiad benchmark, the reference miniF2F set. |
| 170 | trishullab/PutnamBench | https://github.com/trishullab/PutnamBench | 270 | 2026-10-20 | Lean | unknown | D8 | Putnam competition formalizations in Lean, Coq and Isabelle for prover evaluation. |
| 171 | loganrjmurphy/LeanEuclid | https://github.com/loganrjmurphy/LeanEuclid | 144 | 2026-10-13 | Lean | MIT | D8 | Benchmark for autoformalization in Euclidean geometry, scored with Lean. |
| 172 | Sphere-AI-Lab/FormalMATH-Bench | https://github.com/Sphere-AI-Lab/FormalMATH-Bench | 76 | 2026-09-05 | Python | Apache-2.0 | D8 | FormalMATH benchmark for formal mathematical reasoning with LLMs. |
| 173 | mathTensor/AI4Math-Putnam2025 | https://github.com/mathTensor/AI4Math-Putnam2025 | 15 | 2026-10-05 | Lean | MIT | D8 | Lean 4 formalizations of Putnam 2025 problems for prover tests. |
| 174 | rocq-prover/rocq | https://github.com/rocq-prover/rocq | 5611 | 2026-10-20 | OCaml | LGPL-2.1 | D6 | Rocq prover kernel, formerly Coq, one of the seven proof kernels in the lowering target. |
| 175 | rocq-prover/platform | https://github.com/rocq-prover/platform | 247 | 2026-10-12 | Shell | CC0-1.0 | D6 | Multi-platform setup for Rocq and its libraries, a reproducible environment for batch builds. |
| 176 | rocq-prover/opam | https://github.com/rocq-prover/opam | 174 | 2026-10-20 | OCaml | LGPL-2.1 | D6 | Archive of Rocq opam packages, useful for pinning library versions. |
| 177 | rocq-prover/vsrocq | https://github.com/rocq-prover/vsrocq | 462 | 2026-10-20 | Rocq Prover | MIT | D6 | VS Code extension for Rocq, an editor front end for proof checking. |
| 178 | rocq-community/rocq-lsp | https://github.com/rocq-community/rocq-lsp | 210 | 2026-10-19 | OCaml | LGPL-2.1 | D6 | Language server for Rocq, the protocol layer for programmatic proof checking. |
| 179 | rocq-community/coq-nix-toolbox | https://github.com/rocq-community/coq-nix-toolbox | 57 | 2026-10-20 | Nix | MIT | D6 | Nix scripts that automate local Rocq builds and CI, a pinning and reproducibility aid. |
| 180 | sr-lab/coqpyt | https://github.com/sr-lab/coqpyt | 54 | 2026-08-31 | Python | MIT | D6 | Python client for coq-lsp, a scripting interface for proof checking. |
| 181 | ejgallego/pycoq | https://github.com/ejgallego/pycoq | 57 | 2025-11-25 | OCaml | unknown | D6 | Python bindings for Coq, a scripting interface for proof search tools. |
| 182 | LLM4Rocq/rocq-mcp | https://github.com/LLM4Rocq/rocq-mcp | 47 | 2026-10-19 | Python | Apache-2.0 | D6 | MCP server for Rocq, a harness for agent-driven proof checking. |
| 183 | formal-land/rocq-of-rust | https://github.com/formal-land/rocq-of-rust | 1175 | 2026-10-20 | Rocq Prover | unknown | D6 | Translates Rust programs into Rocq models for formal checking, a Rust-to-Rocq route. |
| 184 | formal-land/rocq-of-ocaml | https://github.com/formal-land/rocq-of-ocaml | 277 | 2026-10-18 | OCaml | MIT | D6 | Translates OCaml programs into Rocq for verification, a translation route into the Rocq kernel. |
| 185 | plclub/hs-to-rocq | https://github.com/plclub/hs-to-rocq | 96 | 2026-08-12 | Rocq Prover | MIT | D6 | Converts Haskell source into Rocq, a translation route into the Rocq kernel. |
| 186 | neelsomani/vericuda | https://github.com/neelsomani/vericuda | 134 | 2026-10-15 | Rocq Prover | Apache-2.0 | D6 | Translates Rust GPU code into Coq models as a basis for memory-model proofs. |
| 187 | princeton-vl/CoqGym | https://github.com/princeton-vl/CoqGym | 422 | 2026-10-20 | Coq | LGPL-2.1 | D4 | Learning environment and dataset for theorem proving in Coq, a standard Coq corpus. |
| 188 | coq-tactician/coq-tactician | https://github.com/coq-tactician/coq-tactician | 87 | 2026-10-08 | OCaml | MIT | D5 | Tactic learner and prover for Coq, a data-driven proof-search baseline. |
| 189 | JetBrains-Research/coqpilot | https://github.com/JetBrains-Research/coqpilot | 130 | 2026-10-05 | TypeScript | LGPL-2.1 | D5 | LLM-based proof automation for Coq inside VS Code. |
| 190 | lukaszcz/coqhammer | https://github.com/lukaszcz/coqhammer | 249 | 2026-09-28 | OCaml | NOASSERTION | D5 | Automated reasoning hammer for Rocq, a premise-selection and solver route. |
| 191 | NUS-Program-Verification/AutoRocq | https://github.com/NUS-Program-Verification/AutoRocq | 35 | 2026-10-19 | Python | NOASSERTION | D5 | Agentic theorem prover for Rocq aimed at program verification proofs. |
| 192 | JetBrains-Research/rocqstar-rag | https://github.com/JetBrains-Research/rocqstar-rag | 12 | 2026-10-01 | TypeScript | MIT | D4 | BigRocq utility that prepares Rocq projects for retrieval and training data. |
| 193 | LLM4Rocq/Pile-of-rocq | https://github.com/LLM4Rocq/Pile-of-rocq | 0 | 2026-04-16 | Python | MIT | D4 | Rocq dataset generation pipeline, a corpus for training Rocq models. |
| 194 | andrew-bedford/coqatoo | https://github.com/andrew-bedford/coqatoo | 51 | 2024-05-10 | Java | MIT | D4 | Generates natural language descriptions of Coq proofs, a data-augmentation route. |
| 195 | LLM4Rocq/miniF2F-rocq | https://github.com/LLM4Rocq/miniF2F-rocq | 25 | 2026-09-20 | Rocq Prover | MIT | D8 | Rocq port of miniF2F, a formal olympiad benchmark for Rocq provers. |
| 196 | NUS-Program-Verification/AutoRocq-bench | https://github.com/NUS-Program-Verification/AutoRocq-bench | 6 | 2026-10-05 | Rocq Prover | unknown | D8 | Benchmark of program verification proofs in Rocq for agentic provers. |
| 197 | rocq-community/coq-100-theorems | https://github.com/rocq-community/coq-100-theorems | 62 | 2026-09-16 | HTML | NOASSERTION | D8 | Famous theorems proven in Coq, a small benchmark of standard statements. |
| 198 | PrincetonUniversity/VST | https://github.com/PrincetonUniversity/VST | 511 | 2026-10-18 | Rocq Prover | NOASSERTION | D4 | Verified Software Toolchain in Coq, a large verified C program corpus. |
| 199 | PL-ML/code2inv | https://github.com/PL-ML/code2inv | 106 | 2026-08-12 | SMT | unknown | D5, D8 | Learns loop invariants for program verification, the Code2Inv benchmark and models. |
| 200 | SaswatPadhi/LoopInvGen | https://github.com/SaswatPadhi/LoopInvGen | 65 | 2026-07-07 | OCaml | MIT | D5 | Loop invariant generator for program verification, a classic invariant baseline. |
| 201 | dynaroars/dig | https://github.com/dynaroars/dig | 58 | 2026-10-20 | Python | MIT | D5 | Numerical invariant generation tool, a data-driven invariant baseline. |
| 202 | microsoft/loop-invariant-gen-experiments | https://github.com/microsoft/loop-invariant-gen-experiments | 35 | 2026-07-20 | Python | MIT | D5 | Experiments on LLM loop invariant generation, aimed directly at the invariant stage. |
| 203 | SoftWiser-group/LaM4Inv | https://github.com/SoftWiser-group/LaM4Inv | 30 | 2026-06-22 | SMT | unknown | D5 | LLM invariant candidates checked by bounded model checking, a checked-invariant route. |
| 204 | SoftWiser-group/I3DP | https://github.com/SoftWiser-group/I3DP | 11 | 2026-10-03 | TLA | MIT | D5 | Artifact for automatic inductive invariant generation, an inductive-invariant route. |
| 205 | SoftWiser-group/Clause2Inv | https://github.com/SoftWiser-group/Clause2Inv | 8 | 2026-07-21 | SMT | unknown | D5 | Generate, combine and check framework for invariants through Horn clauses. |
| 206 | bahramabd/llm-bmc-loop-invariants | https://github.com/bahramabd/llm-bmc-loop-invariants | 0 | 2026-06-24 | Python | unknown | D5 | Neuro-symbolic loop invariant inference that pairs LLM output with bounded checking. |
| 207 | aleksandarivke96/InvGen | https://github.com/aleksandarivke96/InvGen | 0 | 2026-10-08 | Python | unknown | D5 | Local-LLM loop invariant generation project, a small-model invariant baseline. |
| 208 | AD1024/veripy | https://github.com/AD1024/veripy | 24 | 2026-04-21 | Python | MIT | D5, D6 | Auto-active verification library for Python, a Python specification route. |
| 209 | ZJU-PL/veripy | https://github.com/ZJU-PL/veripy | 4 | 2026-07-21 | Python | MIT | D5 | Auto-active verifier for Python programs, a second Python specification route. |
| 210 | jwaldmann/matchbox | https://github.com/jwaldmann/matchbox | 3 | 2026-05-27 | Haskell | unknown | D5 | Termination prover, a ranking-function route for termination measures. |
| 211 | ekgma/RevTerm | https://github.com/ekgma/RevTerm | 3 | 2023-12-21 | Java | GPL-3.0 | D5 | Non-termination prover, the complementary side of termination analysis. |
| 212 | robotane/rati | https://github.com/robotane/rati | 0 | 2026-07-29 | Java | Apache-2.0 | D5 | Ranking-based termination and recurrent-set analysis, a measure-inference route. |
| 213 | marcelwa/CEGIS | https://github.com/marcelwa/CEGIS | 79 | 2026-09-30 | C++ | NOASSERTION | D5 | Counterexample-guided inductive synthesis implementation, a route to synthesize checked candidates. |
| 214 | bishoksan/LHornSolver | https://github.com/bishoksan/LHornSolver | 6 | 2023-03-02 | Prolog | Apache-2.0 | D6 | Linear Horn clause solver for non-linear Horn clauses, a checking back end for invariants. |
| 215 | wert310/bmc | https://github.com/wert310/bmc | 1 | 2023-11-07 | Python | MIT | D6 | Bounded model checking solver for nonlinear Horn clauses on Z3, a checking back end. |
| 216 | Mondego/vACT | https://github.com/Mondego/vACT | 5 | 2026-07-01 | Java | GPL-3.0 | D5 | Verifiable specification synthesis with a spec harness, a route that yields checked specs. |
| 217 | Z3Prover/z3 | https://github.com/Z3Prover/z3 | 12804 | 2026-10-21 | C++ | NOASSERTION | D6 | Z3 SMT solver, the back end used by Dafny, Verus, Boogie and other lanes. |
| 218 | cvc5/cvc5 | https://github.com/cvc5/cvc5 | 1375 | 2026-10-21 | SMT | NOASSERTION | D6 | cvc5 SMT solver, the second-solver option for portfolio and budget runs. |
| 219 | bitwuzla/bitwuzla | https://github.com/bitwuzla/bitwuzla | 403 | 2026-10-20 | SMT | NOASSERTION | D6 | Bitwuzla SMT solver for bit-vectors and arrays, a portfolio member. |
| 220 | Boolector/boolector | https://github.com/Boolector/boolector | 359 | 2026-07-27 | SMT | NOASSERTION | D6 | Boolector SMT solver for bit-vector problems, another portfolio member. |
| 221 | OCamlPro/alt-ergo | https://github.com/OCamlPro/alt-ergo | 149 | 2026-10-12 | OCaml | NOASSERTION | D6 | Alt-Ergo SMT prover, a back end used by SPARK and Frama-C WP. |
| 222 | vprover/vampire | https://github.com/vprover/vampire | 441 | 2026-10-20 | C++ | NOASSERTION | D5, D6 | Vampire first-order prover, a premise-selection and hammer back end. |
| 223 | pysmt/pysmt | https://github.com/pysmt/pysmt | 641 | 2026-10-19 | Python | Apache-2.0 | D6 | Python library for SMT formulae across several solvers, a multi-solver harness. |
| 224 | viperproject/smt-scope | https://github.com/viperproject/smt-scope | 86 | 2026-09-24 | Rust | Apache-2.0 | D6 | Analyses and visualizes SMT solver logs, a budget and timing diagnostic. |
| 225 | testsmt/yinyang | https://github.com/testsmt/yinyang | 199 | 2026-10-09 | Python | MIT | D6 | Fuzzing framework for SMT solvers, a harness for solver soundness tests. |
| 226 | JohnLyu2/z3alpha | https://github.com/JohnLyu2/z3alpha | 28 | 2026-10-20 | Python | Apache-2.0 | D6 | Learns Z3 strategies for a given problem, a solver tuning and budget tool. |
| 227 | MachSMT/MachSMT | https://github.com/MachSMT/MachSMT | 28 | 2026-08-28 | Python | unknown | D6 | ML-driven algorithm selection for SMT solvers, a portfolio router. |
| 228 | DebarghaG/proofofthought | https://github.com/DebarghaG/proofofthought | 377 | 2026-10-08 | Python | MIT | D5 | LLM reasoning checked with Z3 proofs, a route that verifies model answers with a solver. |
| 229 | boxed/mutmut | https://github.com/boxed/mutmut | 1498 | 2026-10-21 | Python | BSD-3-Clause | D6 | Python mutation testing system, a mutant generator for Python twin checks. |
| 230 | sixty-north/cosmic-ray | https://github.com/sixty-north/cosmic-ray | 661 | 2026-10-18 | Python | MIT | D6 | Mutation testing for Python, a second mutant generator for twin checks. |
| 231 | agroce/universalmutator | https://github.com/agroce/universalmutator | 168 | 2026-10-20 | Python | NOASSERTION | D6 | Regex-based mutator for generic source code, usable on specs and programs in many languages. |
| 232 | sourcefrog/cargo-mutants | https://github.com/sourcefrog/cargo-mutants | 1346 | 2026-10-20 | Rust | MIT | D6 | Mutation testing for Rust, a mutant generator for Rust and Verus-style twins. |
| 233 | mull-project/mull | https://github.com/mull-project/mull | 846 | 2026-10-20 | C++ | Apache-2.0 | D6 | Mutation testing and fault injection for C and C++, a mutant generator for C twins. |
| 234 | mc-imperial/dredd | https://github.com/mc-imperial/dredd | 15 | 2026-10-08 | C++ | Apache-2.0 | D6 | Mutation testing tool for large C and C++ codebases, another C mutant generator. |
| 235 | githubnext/llmorpheus | https://github.com/githubnext/llmorpheus | 17 | 2026-07-13 | TypeScript | MIT | D6 | LLM-based mutation operators, a mutant generator guided by a language model. |
| 236 | evalplus/evalplus | https://github.com/evalplus/evalplus | 1832 | 2026-10-20 | Python | Apache-2.0 | D8 | EvalPlus, the HumanEval+ and MBPP+ evaluator with pass@k scoring, a direct MBPP-derived yardstick. |
| 237 | bigcode-project/bigcode-evaluation-harness | https://github.com/bigcode-project/bigcode-evaluation-harness | 1063 | 2026-10-13 | Python | Apache-2.0 | D8 | Code-generation evaluation harness with pass@k scoring, a standard harness to adapt. |
| 238 | Smfakhoury/awesome-llm-specifications | https://github.com/Smfakhoury/awesome-llm-specifications | 0 | 2026-10-15 | Python | CC0-1.0 | D8 | Curated list of LLM specification papers, benchmarks and tools, a guide to other yardsticks. |
| 239 | usi-verification-and-security/SMT-LIB-benchmarks | https://github.com/usi-verification-and-security/SMT-LIB-benchmarks | 0 | 2022-06-08 | unknown | unknown | D8, D6 | SMT-LIB benchmark collection, a solver benchmark set (description empty, name-based). |
| 240 | Goedel-LM/Goedel-Prover | https://github.com/Goedel-LM/Goedel-Prover | 240 | 2026-10-18 | Python | MIT | D5 | Open model for automated formal proof generation on math problems, a Lean 4 prover baseline. |
| 241 | deepseek-ai/DeepSeek-Prover-V2 | https://github.com/deepseek-ai/DeepSeek-Prover-V2 | 1314 | 2026-10-21 | unknown | NOASSERTION | D5 | Lean 4 prover that splits theorems into subgoals, an open baseline for prover comparisons. |
| 242 | Goedel-LM/Goedel-Prover-V2 | https://github.com/Goedel-LM/Goedel-Prover-V2 | 194 | 2026-10-15 | Jupyter Notebook | unknown | D5 | Second-generation Goedel prover family (description empty, name-based). |
| 243 | deepseek-ai/DeepSeek-Prover-V1.5 | https://github.com/deepseek-ai/DeepSeek-Prover-V1.5 | 588 | 2026-10-21 | Python | MIT | D5 | Predecessor of DeepSeek-Prover-V2, a Lean 4 prover baseline (description empty, name-based). |
| 244 | ByteDance-Seed/Seed-Prover | https://github.com/ByteDance-Seed/Seed-Prover | 441 | 2026-10-08 | Lean | Apache-2.0 | D5 | ByteDance Seed prover repository, a recent prover reference (description empty, name-based). |
| 245 | MoonshotAI/Kimina-Prover-Preview | https://github.com/MoonshotAI/Kimina-Prover-Preview | 378 | 2026-10-20 | Python | unknown | D5 | Technical report for Kimina-Prover Preview, a Lean 4 prover reference. |
| 246 | goedelcodeprover/Goedel-Code-Prover | https://github.com/goedelcodeprover/Goedel-Code-Prover | 146 | 2026-10-07 | Lean | MIT | D5 | Code prover that splits a target into sub-lemmas, a decomposition route for verified code. |
| 247 | sunblaze-ucb/verina | https://github.com/sunblaze-ucb/verina | 83 | 2026-10-14 | Lean | Apache-2.0 | D8 | Verina benchmark for verifiable code generation, scoring code, specifications and proofs in Lean. |
| 248 | trishullab/clever | https://github.com/trishullab/clever | 49 | 2026-10-05 | Lean | MIT | D8 | CLEVER benchmark of formally verified code generation in Lean 4, built from HumanEval problems. |
| 249 | haoyuzhao123/algoveri | https://github.com/haoyuzhao123/algoveri | 9 | 2026-09-25 | Rust | Apache-2.0 | D8 | Codebase for the AlgoVeri benchmark of classical algorithms verified in Dafny, Verus and Lean. |
| 250 | microsoft/intent-formalization | https://github.com/microsoft/intent-formalization | 30 | 2026-09-14 | Python | MIT | D8 | Evaluation artefacts for translating natural-language intent into formal specs, formerly nl-2-postcond. |

## Top 25 to try first

1. #1 sun-wendy/DafnyBench: main Dafny verification benchmark; runs locally with a Dafny install.
2. #3 dafny-lang/miniF2F: Dafny port of miniF2F, a formal math set small enough for one machine.
3. #18 Beneficial-AI-Foundation/vericoding-dafny-benchmark: Dafny task set from the vericoding family for benchmark runs.
4. #19 Beneficial-AI-Foundation/vericoded-dafny-benchmark: second Dafny task set from the same family for cross-checking numbers.
5. #67 Beneficial-AI-Foundation/vericoding-verus-benchmark: Verus task set from the vericoding family for the Verus lane.
6. #68 Beneficial-AI-Foundation/vericoded-verus-benchmark: second Verus task set from the same family for cross-checking.
7. #51 secure-foundations/human-eval-verus: HumanEval tasks in Verus, a direct MBPP-style yardstick.
8. #52 HIPREL-Group/VeriContest: competitive-programming verification benchmark, closest to the panel task shape.
9. #53 verus-lang/verus-spec-check: tests Verus specs for soundness and completeness, a twin-style check to run locally.
10. #49 microsoft/verus-proof-synthesis: Verus proof synthesis code with its benchmark, runnable on one machine.
11. #48 verus-lang/verus: the Verus kernel itself, needed for every Verus check.
12. #17 JetBrains-Research/HumanEval-Dafny: HumanEval translated into Dafny, a verified-code set for local runs.
13. #24 NVictor2004/dafny-equivalence-benchmarks: equivalent and non-equivalent Dafny functions, a labelled set for twin-style tests.
14. #25 NVictor2004/equidafny: Dafny equivalence checker, a twin-style check for generated functions.
15. #10 metareflection/dafny-replay-bench: Dafny proof benchmark with replay tooling, small enough for one machine.
16. #236 evalplus/evalplus: HumanEval+ and MBPP+ evaluator with pass@k scoring, direct to the MBPP-derived panel.
17. #237 bigcode-project/bigcode-evaluation-harness: pass@k code-generation harness that runs on one machine.
18. #162 zhangir-azerbayev/ProofNet: undergraduate formal math benchmark, a Lean yardstick.
19. #165 facebookresearch/miniF2F: formal olympiad benchmark for Lean provers, runnable locally.
20. #155 lean-dojo/LeanDojo: data extraction and Lean interaction, a route to Lean training data.
21. #154 lean-dojo/ReProver: retrieval-augmented Lean prover, a baseline that fits one GPU.
22. #161 dwrensha/compfiles: formalized competition problems in Lean, a small benchmark set.
23. #145 JOSHCLUNE/LeanHammer: hammer for Lean combining premise selection with solver calls.
24. #248 trishullab/clever: formally verified code generation in Lean built from HumanEval problems.
25. #229 boxed/mutmut: Python mutation testing, a mutant generator for Python twin checks.
