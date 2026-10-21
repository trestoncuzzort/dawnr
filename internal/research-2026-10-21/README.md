# Research library for dawnr (2026-10-21)

Four lists gathered by four Haiku scouts in one pass on 2026-10-21 (UTC), every entry taken from a search result or
API response the scout saw in its session (none from memory), tagged against dawnr's open issues, not yet read in
depth. Each file ends with a "Top 25" section.

| file | what | how | counts |
|---|---|---|---|
| [`papers-A.md`](papers-A.md) | 250 papers on specification synthesis, repair turns, verifier rewards, small models | 94 arXiv API queries, 19 WebSearch | D1 103, D2 111, D3 61, D7 71; 237 arXiv links |
| [`papers-B.md`](papers-B.md) | 250 papers on training data, invariant and proof synthesis, several provers, benchmarks | 90 arXiv API queries, 20 WebSearch | D4 72, D5 149, D6 69, D8 116; 246 arXiv links |
| [`repos-A.md`](repos-A.md) | 250 repositories: spec tools, repair loops and agents, RL trainers, serving and decoding | 462 `gh search repos` calls, 35 `gh repo view`, 23 WebSearch; pool 22,191 | D1 45, D2 82, D3 83, D7 70; 184 permissive licences |
| [`repos-B.md`](repos-B.md) | 250 repositories: datasets, invariant generators, kernels and translation, benchmarks | 259 `gh search repos` calls, 8 `gh repo view`, 12 WebSearch | D4 47, D5 59, D6 101, D8 47; 158 permissive; star median 30 |

Two focused lists followed the same day, each from one Haiku scout on the issue that had just stopped the work:

| file | issue | counts |
|---|---|---|
| [`spec-skill-scout.md`](spec-skill-scout.md) | teaching a 4B student to write specifications: distillation, self-training with checkers, selection among candidates, why small models misread problems, verifier-reward RL | 150 papers, 100 repositories; S1 71, S2 25, S3 40, S4 29, S5 26 (papers); 52 permissive repositories |
| [`teacher-scout.md`](teacher-scout.md) | an open-weight teacher for specifications on one 16 GB card: models, measured comparisons, distillation pipelines, running larger models on 16 GB, licence facts | 120 papers, 80 repositories, 50 model cards; 39 of 50 models Apache-2.0 or MIT; a Top 15 ranked for the RTX 4080 |

Distinct across the pairs: 404 papers (96 arXiv ids appear in both paper lists) and 461 repositories (39 appear
in both repository lists). Checks run on 2026-10-21: 250 numbered rows per file, no duplicate links inside a
file, no em or en dashes, ten sampled links per paper list and eight per repository list resolve with the stated
title or repository.

Issue key: D1 specification synthesis (pre and postconditions from English, tests and code; spec quality and
vacuity) · D2 repair turns (verifier errors and counterexamples fed back; search under a call budget) · D3
verifier-based reward and RL (dense obligation rewards, GRPO and expert iteration with provers, reward hacking) ·
D4 training data (decomposition, mutation, synthetic corpora, self-distillation, contamination) · D5 invariant,
annotation and proof synthesis · D6 several provers (translation between verification languages, twins and
vacuity, solver budgets, common-mode failures) · D7 small models on minimal resources (4B to 8B, quantized
serving, constrained decoding, inference-time scaling) · D8 benchmarks and evaluation.

Caveats the scouts reported: "why" cells rest on titles, abstracts and search snippets, not full reads; venues are
stated only where a result showed them; 21 rows of `repos-B.md` are tagged from the repository name alone (empty
descriptions); licences are gh's SPDX keys, with NOASSERTION ("other") on Dafny, Z3, cvc5, DeepSeek-Prover-V2
and EAGLE, GPL-3.0 on AdaCore/spark2014, AGPL on AlphaCodium, sisyphus and ax-prover-base; a few expected
repositories did not surface in gh results (Frama-C and Rocq main repositories, SpecGen, Vero, FVEL, Clover,
Lemur, Kimina) and are absent rather than invented.

## What the results so far say the library should be used for

The repair turn at the specification stage (queue row 2, `t/PREDICT-2026-10-21-repair-turn.md`, measured
2026-10-21) moved kept specifications 18 to 21 and answers 13 to 16 and left the clean count at 6 of 95: the 4B
student rewrites when shown the test it fails and either repeats its error or fits the three tests. The next
rows are on the training side, so read first:

| issue | first things to take from the library |
|---|---|
| D3 dense reward | the per-obligation reward and verifier-RL rows of `papers-A.md` (its Top 25) and the trainers wired to provers in `repos-A.md` (TRL, verl, OpenRLHF, SkyRL rows) |
| D4 repair rows and mutated tasks | the decomposition, mutation and self-distillation rows of `papers-B.md`; the dataset generators of `repos-B.md` |
| D1 specification synthesis | the test-to-spec and code-to-contract rows of `papers-A.md` (nl2postcond, SpecGen, AutoSpec lineage); spec-quality and vacuity tools in `repos-A.md` |
| D8 public yardsticks | DafnyBench, Vericoding, VerusBench, AlgoVeri, CLEVER rows of `repos-B.md` and `papers-B.md` (queue row 5) |
| D6 kernels | translation and twin tooling in `repos-B.md` for the E2 cvc5 and Lean mvcgen probes (queue row 6) |

Ideas from this library go to dawnr only: nothing here enters training rows or the public mirror.
