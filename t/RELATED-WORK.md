# What others do, and the gaps t and tup fill

A related-work landscape for the whole project, written 2026-09-09.

## How this was produced, and how far to trust it

Nine facet searches and three gap-angle searches ran over the public web
(web search plus a fetched page for every candidate returned), yielding 232
distinct candidates. 42 of them were read against their own source by an
agent that wrote a facet-by-facet comparison with verbatim quotes; every
read was then checked by a second agent for whether the source exists and
says what was claimed (3 were dropped as inaccurate: a duplicate
"Vericoding Benchmark" entry with wrong citation details, a Viper entry
that mislisted its frontends, and a nanoda entry with the wrong author),
and by a skeptic arguing the closeness down. The closeness given below is
the minimum of those readings, on a 1 to 5 scale where 5 means the same
mechanism and 1 means only the same topic. Nothing reached 5 after the
skeptic pass; four items sit at 3.

A final pass by hand added five things the search found but the capped
read stage dropped, each checked directly against its source on
2026-09-09: Federated Formal Verification, hax, Trustix, the Lean Kernel
Arena's current numbers, and two RL-with-verifier-reward papers. Items
marked "sweep only" below were fetched once by a searcher and not read in
depth. Everything here is absence of evidence within this search, never
proof of novelty; the search did not cover paywalled proceedings beyond
their abstracts, non-English venues, or industrial work with no public
page.

## 1. The answer

Nobody in this search does the combination. Stated as five pillars: one
specification interlingua (a), lowered mechanically to several
independently built and logically different proof kernels (b), graded by a
cross-kernel table that requires the real program verified and a
witness-chosen mutant twin refuted through a certificate the kernel itself
checks, gated for coherence (c), used as a training reward for a model
(d), inside an operating system whose every file and build step carries a
receipt (e). No candidate stacks more than two of the five, and the two
that come closest to (b) plus (c) are both from 2026 and both check a
single fixed logic or a single spec language rather than a lowered
program.

The nearest neighbours to the whole, by pillar:

- **Federated Formal Verification** (Pierre Falda, arXiv 2606.02019,
  submitted 2026-06-01). One TLA+ specification whose obligations are
  discharged across many heterogeneous backends, with "cross-axis
  convergence" composing "per-obligation verdicts across independent
  verifiers into operational kernel-agreement gates", "cross-backend
  citation" discharging an obligation by citing an equivalent theorem in a
  structurally distinct kernel, and an AI layer treated as "untrusted
  proof-search labour inside a trusted CI envelope". This is the closest
  thing to the agreement table. It differs in every other pillar: the
  source is a TLA+ model of a running system, not a task language a model
  writes; obligations are cited across kernels rather than one program
  lowered whole to each; there is no mutant, no witness, no refutation
  certificate; the AI is a proof searcher, not the thing being trained.
  Its anti-drift mechanism (closure-assertion directives such as Coq's
  Print Assumptions and Lean's #print axioms enforced at build level) is
  worth taking (section 3).
- **Lean Kernel Arena** (leanprover, arena.lean-lang.org, checked
  2026-09-09: 19 checkers, 204 tests, 114 known-valid and 73 known-invalid
  proofs plus 15 corner cases, outcomes accept, reject, decline, crash).
  The agreement-table instinct and the ground-truth grading shape (accept
  the true, reject the false) are the same. The object is one exported
  proof term in one logic read by reimplementations of one kernel; nothing
  is translated, so a mistranslation shared by all checkers is exactly
  what it cannot see. Leonardo de Moura's "Who Watches the Provers?"
  (leodemoura.github.io, 2026-03-16) states the argument the Arena runs
  on, with the 2022 Lean kernel arithmetic bug that nanoda did not share
  as evidence; **Comparator** (github.com/leanprover/comparator) is the
  same move packaged for adversarial submissions, with an exact-match
  check on the theorem statement as its gate.
- **SV-COMP** (Beyer, TACAS 2024, doi.org/10.1007/978-3-031-57256-2_15):
  59 verifiers and 17 witness validators over 30,300 C tasks; a verdict
  scores only when an independent validator confirms its witness, and
  wrong proofs and false alarms are headline statistics with asymmetric
  penalties. Same program in the same language for every tool, no
  interlingua, no mutant per task. The witness format (YAML 2.0) and the
  validator track are the mature version of what t's refutation
  certificate does for one twin.
- **hax** (Cryspen, github.com/cryspen/hax, checked 2026-09-09): a
  mechanical translator of a large Rust subset into Lean (via Aeneas), F*
  and Rocq, plus protocol backends. This is the closest thing to t's
  lowering: one source, several logically different kernels, by a compiler
  rather than a model. It has no cross-backend agreement requirement, no
  twin, no certificate, and its source is a full language, not a spec
  interlingua a model is meant to write. Why3 (Filliâtre and Paskevich,
  ESOP 2013), Boogie and Viper are the older shape of the same idea, and
  Why3 is a literal dependency under two of t's seven kernels (SPARK and
  Frama-C WP).
- **A Benchmark for Vericoding** (Bursuc et al., arXiv 2509.22908; 12,504
  tasks across Dafny, Verus and Lean, translated by an LLM
  generate-verify-repair loop and judged by an LLM) and **AlphaVerus**
  (Aggarwal, Parno, Welleck, arXiv 2412.06176; DafnyBench translated to
  Verus with a critique stage against reward hacking) are the nearest on
  lifting a corpus across kernels and on the reward-hacking finding. Both
  settle fidelity by verifier acceptance plus an LLM judge, never by an
  equivalence lemma or differential execution, and neither requires
  agreement across kernels.
- **StageX** (codeberg.org/stagex/stagex) and the **Guix full-source
  bootstrap** (357-byte seed, 2023) are the nearest to tup's receipted
  build; **Trustix** (nix-community, checked 2026-09-09) "compares build
  outputs for a given build input across a group of independent providers"
  through signed Merkle logs, the multi-builder form of tup's witness
  files. None of them touches proof kernels.

## 2. The gaps t and tup fill

Each is a mechanism no candidate in this search has; the nearest thing is
named so the claim can be checked.

1. **Agreement across kernels on a translated program.** Arena and
   Comparator agree on one proof term; SV-COMP on one C program; Federated
   Formal Verification on one TLA+ obligation cited to whichever kernel
   holds an equivalent theorem. t is the only one where seven kernels each
   receive their own lowering of the same task and the table is the
   instrument, so a translation defect appears as a column that disagrees.
2. **The twin as a per-cell requirement.** Mutation to test specification
   strength exists in one kernel at a time: MutDafny (Amaral, Mendes,
   Campos, arXiv 2511.15403; 40 operators, 794 programs, 5 weak specs
   found), mCoq (proof mutation), SpecFuzzer (arXiv 2201.10874, mutant
   kill used to rank inferred assertions), "Beyond Postconditions" (arXiv
   2510.12702, mutation score for LLM-inferred contracts, sweep only), and
   the vacuity line from Beer et al. (IBM, 2001) through mutation-based
   vacuity (ACM 2010, sweep only). All of them read a surviving mutant as a
   weak spec. None makes "real verified and twin refuted" the condition
   for a cell to count, none picks the twin by a measured concrete witness
   and hands the witness to the kernel as a refutation obligation, and
   none has the coherence gate (a certificate on a file the main run
   verified reads MALFORMED). Alethe and Carcara (SMT proof certificates
   with an independent Rust checker, sweep only) certify a proof, not a
   refutation of a program.
3. **Ground-truth fuzzing of a lowering that fans out.** Testing Dafny
   (Irfan et al., ISSTA 2022, XDsmith: 31 bugs, verdict known by
   construction) fuzzes one verifier; fuzz-d and DafnyFuzz fuzz Dafny's
   compilers; "Crash-free Deductive Verifiers" (arXiv 2604.19448, sweep
   only) fuzzes Dafny, VeriFast, Viper and VerCors for crashes;
   model-based testing of Boogie (arXiv 2508.17895, sweep only) tests one
   IVL against an operational semantics. Nobody grades seven translations
   of the same generated task against a truth fixed before any kernel
   runs, which is what makes a shared mistranslation visible.
4. **A lifter with formal fidelity.** Vericoding's SpecTranslator,
   AlphaVerus's Dafny2Verus and MiniF2F-in-Rocq (arXiv 2503.04763, sweep
   only) translate corpora by LLM and accept on verifier success plus an
   LLM opinion. t's lifter verifies equivalence lemmas in Dafny and runs
   differential execution against the interpreter, and records refusals
   by reason. "Why Just Boogie?" (arXiv 1601.00516, Boogie to WhyML,
   sweep only) is the one mechanical, evaluated IVL-to-IVL translation in
   the list and is the right precedent to cite for the lifter's design.
5. **The reward-hacking measurement, and what it says the reward is.**
   Three 2025 and 2026 papers meet the same fact: "Automating Formal
   Verification with Reinforcement Learning and Recursive Inference" (Max
   Tan, arXiv 2605.30914, checked 2026-09-09) trains with GRPO against
   Dafny and reports "specification hacking, where models exploit weak
   formal specifications instead of implementing the intended solutions",
   answered by "filtering underspecified and vulnerable tasks"; Re:Form
   (Yan et al., arXiv 2507.16331, checked 2026-09-09) trains with Dafny
   feedback and "RL with regularization"; AlphaVerus filters with LLM
   critics after showing the model snowballs into assume(false). t
   measured the same failure on MBPP (35 of 64 well-formed specs restate
   the body, 8 of the 10 verified-but-wrong tasks are of that shape) and
   defines the reward as verified-with-refuted-twin AND tests, with the
   twin and the tests both kernel- or execution-checked rather than
   model-judged. That definition, and the fact that fstar's
   zero-obligation rule reads the restated specs as MALFORMED on its own,
   are not in any candidate. Clover (arXiv 2310.17807) checks docstring,
   code and annotation consistency with LLM equivalence, the model-judged
   version of the same concern.
6. **Receipts on the instrument, not only on the artifact.** Reproducible
   Builds, Guix, Nix, StageX, in-toto, SLSA and OmniBOR receipt the build
   of software. Nothing in the list publishes each measured number beside
   the pinned instrument that produced it, keeps third-party reproduction
   files in the repository, or inventories a distribution at file level
   with no package manager as the manifest. This is the weakest of the
   six claims: the pieces exist separately (Trustix's multi-builder logs,
   Debian buildinfo files, jhalfs for automating the LFS book), and tup's
   difference is doing it to the machine the model runs on and refusing to
   call the result verified.

## 3. What others have that t and tup lack, and should take

- **A decline outcome.** Arena separates decline (a construct the checker
  does not support) from reject and crash and does not penalise it. t's
  abstain is the same thing in the lifter and the sweep; the census should
  say so in the table's legend and never fold abstain into failure.
- **Asymmetric scoring.** SV-COMP charges a wrong proof twice a false
  alarm. The sweep table counts cells; a score that weights a REFUTES-TRUE
  or UNSOUND cell far above an UNPROVED one would say what the table means
  in one number.
- **Closure assertions as anti-drift.** Federated Formal Verification
  enforces Print Assumptions and #print axioms at build level. t has the
  coherence gate and rocq's coqchk assumption list; the same directive for
  lean (#print axioms on the theorem), fstar (admit and assume scans, which
  the adapter already bans) and verus (no assume, no external_body) should
  be one rule across columns, stated in SPEC.md.
- **Independent checkers as extra columns at no design cost.** Comparator's
  pattern (replay the Lean export through nanoda and lean4checker) turns
  one lean cell into three verdicts for the price of two subprocesses;
  Carcara can check the SMT proofs behind dafny and verus cells. These are
  the de Bruijn move at the layer where t's trust actually bottoms out.
- **A proved lowering for one column.** "Towards Trustworthy Automated
  Program Verifiers" (Parthasarathy et al., PLDI 2024, arXiv 2404.03614)
  emits a checked Isabelle proof per run that the Viper-to-Boogie
  translation preserves correctness. t's far field names the CakeML path;
  this is the nearer one, and one column (dafny or verus) with a proved
  lowering would answer the "agreement is not proof" objection directly.
- **Multi-builder witness.** Trustix and StageX (two independent
  maintainers rebuild and sign before trust) are the form tup's witness
  files should grow into once a second builder exists; in-toto attestation
  is the format to write receipts in so other tools can read them.
- **Task filtering before RL.** Tan's filtering of "underspecified and
  vulnerable tasks" and Verus-SpecGym's adversarial hacks (arXiv
  2605.26457) as oracle are cheap complements to the twin: filter the
  corpus once, then let the twin and tests grade what is left.
- **hax's Rust route.** A Rust source with Lean, F* and Rocq backends is
  a second interlingua already used by a company; where t's tasks can be
  rendered as Rust, hax gives three kernels' verdicts for comparison with
  t's own lowerings of the same task.
- **AgentFS** (penberg.org, sweep read) captures every tool call and
  snapshots the live filesystem of an agent as one file; it is the
  runtime half of tup's "what did the agent change on disk" claim, which
  tup so far answers only at build time.

## 4. Per facet, what exists

Closeness is the post-skeptic minimum; "checked" means fetched and read by
hand on 2026-09-09 in addition to the workflow's verification.

| Candidate | Facet | Closeness | Shares | Lacks |
|---|---|---|---|---|
| Federated Formal Verification (Falda 2026) | multi-kernel agreement | 3 (checked) | kernel-agreement gates over independent verifiers, closure assertions | a lowered program per kernel, twin, certificate, reward |
| Lean Kernel Arena | multi-checker trust, ground truth | 3 (checked) | accept/reject grading of many checkers | translation, twin, reward |
| SV-COMP 2024 | multi-checker trust | 2 (contested) | witness validation by independent tools, disagreement as metric | interlingua, twin per task |
| Comparator | multi-checker trust | 2 | replay through two kernels, statement match gate | heterogeneous logics, twin |
| Who Watches the Provers? | multi-checker trust | 2 | the argument, a documented kernel bug | any translation step |
| hax (Cryspen) | interlingua | 3 (checked) | mechanical lowering of one source to Lean, F*, Rocq | agreement table, twin, spec-first source |
| Why3 | interlingua | 2 (contested) | one IVL to many provers, dependency of two columns | agreement table, twin, fuzzing of its own drivers |
| TPTP/TSTP, CASC | interlingua, benchmark | 3 | one format, many provers, SZS verdict vocabulary | programs, translation, twin |
| OpenTheory | interlingua | 3 | portable proof replayed by several HOLs | heterogeneous logics, twin |
| Dedukti/Logipedia | interlingua | sweep only | universal proof term language across Coq, Lean, HOL, Isabelle | programs, agreement grading |
| Viper, Boogie | interlingua | sweep only | IVL with several frontends and two backends | agreement grading, twin |
| Trustworthy Automated Program Verifiers (PLDI 2024) | proved lowering | 2 | checked proof that a translation preserves correctness | several backends, empirical agreement |
| MutDafny | spec mutation | 2 (contested) | body mutants as weak-spec signal | cross-kernel requirement, certificate, gate |
| SpecFuzzer, mCoq, Beyond Postconditions | spec mutation | 3, 3, sweep | mutant kill as spec quality | per-cell requirement, witness, certificate |
| Vacuity detection (Beer et al. 2001; mutation-based 2010) | vacuity | 3, sweep | vacuous pass as a first-class verdict | program twins, kernels |
| Alethe / Carcara | certificates | sweep only | SMT proof certificates checked independently | refutation of a program |
| Automating FV with RL (Tan 2026) | LLM reward | 3 (checked) | GRPO against Dafny, names specification hacking | several kernels, twin, tests in the reward |
| Re:Form (Yan et al.) | LLM reward | sweep, checked abstract | RL with Dafny feedback, DafnyComp | several kernels, twin |
| AlphaVerus | LLM reward, lifting | 2 (contested) | DafnyBench to Verus, critique against reward hacking | kernels beyond one, formal fidelity |
| A Benchmark for Vericoding | benchmark, lifting | 2 (contested) | 12,504 tasks over three kernels, cheating filter | agreement across kernels, formal fidelity |
| DafnyBench, MBPP-DFY (Misu et al.), Verina, Clover, SpecCoder, Verus-SpecGym | benchmarks | 2 to 3 | the corpora and the single-kernel grading t lifts from | cross-kernel grading, twins |
| Testing Dafny / XDsmith | verifier fuzzing | 3 | verdict known by construction | several kernels, a lowering to fuzz |
| fuzz-d, DafnyFuzz, Crash-free Deductive Verifiers, Boogie MBT | verifier fuzzing | sweep only | fuzzing verifiers and IVLs | ground truth across a fan-out |
| Why Just Boogie? | lifting | sweep only | evaluated IVL-to-IVL translation | model-written source, agreement |
| StageX | receipted build | 2 (contested) | 181-byte seed, hermetic hash-locked builds, two-maintainer quorum | bootable OS, any proof |
| Guix full-source bootstrap, Bootstrappable Builds | receipted build | sweep read, 4 by reader | 357-byte seed, content-addressed store | file-level inventory as manifest, witness files |
| Trustix | receipted build | checked | multi-builder consensus on build outputs | OS image, proof |
| in-toto, SLSA, OmniBOR, Witness, Reproducible Builds, Debian buildinfo | provenance | sweep only | attestation formats and reproducibility practice | the instrument side |
| jhalfs / ALFS | LFS automation | sweep only | the LFS book turned into a driver | receipts, witnesses |
| seL4, CertiKOS, Hyperkernel, IronFleet, CompCert, CakeML, DeepSpec, PCC, DDC | verified substrate | 2, rest sweep | proof reaching a running artifact, verified toolchains, trusting-trust answers | several kernels, general task language |
| AgentFS, Sigstore model-transparency, Atlas, E2B, Wolfi | accountable AI environment | 3, rest sweep | audit of agent changes, signed models, sandboxes | build-time receipts, proof |
| AWS Automated Reasoning, DARPA HACMS, Galois, AdaCore, Cryspen | industry and programs | 2 to 3 | formal methods in production, two of t's kernels in use | interlingua, agreement, twin |
| QED Manifesto | history | 2 | mechanised checking as the unit of trust, never built | everything else |

## 5. Reading list for the paper

Ranked by how much each changes what the paper has to say.

1. Falda, "Federated Formal Verification: Cross-Backend Citation, Cross-Axis Convergence, and AI-Orchestrated Proof Dispatch for Production Systems", arXiv 2606.02019 (2026). The nearest claim to the agreement table; the paper must position against it.
2. Lean Kernel Arena (arena.lean-lang.org) and de Moura, "Who Watches the Provers?" (2026). The argument and the running instance for many independent checkers.
3. Beyer, "State of the Art in Software Verification and Witness Validation: SV-COMP 2024", TACAS 2024. Witness validation and disagreement as headline metrics at scale.
4. Cryspen, hax (github.com/cryspen/hax). One Rust source mechanically lowered to Lean, F* and Rocq.
5. Filliâtre and Paskevich, "Why3: Where Programs Meet Provers", ESOP 2013. The ancestor of one spec, many provers, and a dependency of two columns.
6. Tan, "Automating Formal Verification with Reinforcement Learning and Recursive Inference", arXiv 2605.30914 (2026), and Yan et al., "Re:Form", arXiv 2507.16331. RL against a verifier and specification hacking, the failure 12.6 measured.
7. Aggarwal, Parno, Welleck, "AlphaVerus", arXiv 2412.06176. DafnyBench lifted to one kernel, reward hacking named and filtered.
8. Bursuc et al., "A Benchmark for Vericoding", arXiv 2509.22908. The multi-kernel benchmark to compare the spec experiment against.
9. Irfan, Porncharoenwase, Rakamarić, Rungta, Torlak, "Testing Dafny", ISSTA 2022. Ground truth by construction for one verifier.
10. Amaral, Mendes, Campos, "MutDafny", arXiv 2511.15403. The single-kernel form of the twin.
11. Parthasarathy, Dardinier, Bonneau, Müller, Summers, "Towards Trustworthy Automated Program Verifiers", PLDI 2024. The proved-lowering alternative to agreement.
12. Loughridge et al., "DafnyBench", arXiv 2406.08467, and Misu et al., "Towards AI-Assisted Synthesis of Verified Dafny Methods", arXiv 2402.00247. The corpora the lifter and the spec experiment consume.
13. Klein et al., "seL4", SOSP 2009; Kumar et al., CakeML; Wheeler, Diverse Double-Compiling. The verified substrate and trusting-trust lineage tup names as its horizon.
14. Guix, "The full-source bootstrap" (2023); StageX; Trustix. The receipted-build lineage and the multi-builder form of the witness.
15. Sutcliffe, TPTP and CASC; Hurd, OpenTheory (NFM 2011). Thirty years of one format, many provers.

## Appendix: every candidate the search found

Grouped by the facet the searcher filed it under, with the searcher's
closeness before any reading (inflated: 111 of 232 were filed at 4 or 5,
and none survived reading above 3). Use it as a checklist, not as
evidence.

### rlvr (7)

- [4] "Automating Formal Verification with Reinforcement Learning and Recursive Inference" (thesis) (paper) https://arxiv.org/pdf/2605.30914 : Trains open-source models with GRPO/RLVR scored by Dafny compiler+verifier outcomes (2.2%→58.1% verified reward on an APPS-derived set) and separately explores Lean inference-time search; documents 'specification hacking'.
- [4] Automating Formal Verification with Reinforcement Learning and Recursive Inference (Dafny/APPS RLVR) (paper) https://arxiv.org/pdf/2605.30914 : RLVR training on an APPS-derived Dafny dataset that explicitly names 'specification hacking' ,  models exploiting weak formal specs instead of the intended solution ,  as the failure mode discovered once verified reward rose from 2.2% to 58.1%.
- [4] Re:Form (Reducing Human Annotations in Scalable Formal Software Verification with RL in LLMs) (paper) https://arxiv.org/pdf/2507.16331 : RL-trains LLMs on Dafny proof generation using verifier-acceptance as the reward signal, explicitly analyzing failure modes where trivial/hollow proofs satisfy the checker.
- [3] AlphaProof (software) https://www.nature.com/articles/s41586-025-09833-y : DeepMind system combining an LLM formalizer with an AlphaZero-style RL solver whose reward is the Lean kernel's binary proof-accept/reject signal; solved IMO 2024 problems at silver-medal level.
- [3] DeepSeek-Prover-V1.5 / V2 (software) https://arxiv.org/pdf/2408.08152 : Lean 4 theorem prover trained with online RL where Lean's verification outcome (proof accepted or not) is the sparse binary reward, plus MCTS at inference.
- [2] Aletheia: What Makes RLVR For Code Verifiers Tick? (paper) https://arxiv.org/pdf/2601.12186 : Controlled ablation study of RLVR training recipes (on-policy learning, thinking traces, negative samples) for training LLM-based CODE verifiers, not proof-kernel verifiers.
- [2] Kimina-Prover / Goedel-Prover-V2 (software) https://arxiv.org/pdf/2504.11354 : Large-scale RL (Kimi k1.5 pipeline) formal reasoning models for Lean 4 theorem proving, state of the art on miniF2F.

### de bruijn criterion (6)

- [5] nanoda / nanoda_lib (software) https://github.com/ammkrn/nanoda_lib : Independent from-scratch Lean kernel/typechecker written in Rust that has caught real soundness bugs the official Lean 4 kernel missed (2022 arithmetic bug), used as an external cross-checker.
- [5] Who Watches the Provers? (paper) https://leodemoura.github.io/blog/2026-3-16-who-watches-the-provers/ : Leonardo de Moura's essay arguing proof assistants should rely on plural, independent, interchangeable kernels rather than a single trusted core, using the 2022 Nanoda-catches-Lean-bug incident and the Lean Kernel Arena as evidence that disagreement between checkers is the trust mechanism.
- [4] lean4checker (software) https://github.com/leanprover/lean4checker : Strict, minimal external re-checker for compiled Lean 4 .olean environments, used by the Lean FRO as an independent verification pass distinct from the elaborator/compiler pipeline.
- [4] Postmortem for Kernel Soundness Bug #14576 (paper) https://leodemoura.github.io/blog/2026-8-1-postmortem-for-kernel-soundness-bug-14576/ : De Moura's postmortem of a Lean 4 kernel soundness bug, discussing how it was found/handled and reinforcing the case for multiple independent checkers as a detection mechanism.
- [4] trepplein / trepplein4 (software) https://github.com/gebner/trepplein : Independent reference type-checker for Lean (Scala), one of the earliest external checkers built specifically to satisfy the de Bruijn criterion; trepplein4 extends it to Lean 4.
- [3] coqchk (software) https://coq.inria.fr/ : Coq's own independent re-checking tool that re-runs the kernel over a compiled library to catch incomplete proofs, added axioms, or proofs checked under inconsistent settings ,  a built-in de-Bruijn-criterion pass distinct from the interactive elaborator.

### compiler fuzzing (5)

- [4] DafnyFuzz (software) https://www.doc.ic.ac.uk/~afd/papers/2025/ICST-Industry.pdf : Another Dafny random program generator used in CI at the Dafny project to catch compiler/verifier regressions via differential testing across targets.
- [4] fuzz-d (software) https://www.imperial.ac.uk/media/imperial-college/faculty-of-engineering/computing/public/distinguished-projects/2223-ug-projects/fuzz-d-Random-Program-Generation-for-Testing-Dafny.pdf : Random Dafny program generator focused on catching miscompilation across Dafny's multiple compilation targets via differential testing.
- [3] Csmith (software) https://github.com/csmith-project/csmith : Random C-program generator for differential compiler testing; found 325+ bugs across GCC/Clang and unproved parts of CompCert.
- [3] Finding and Understanding Bugs in C Compilers (Csmith paper, Yang et al. PLDI'11) (paper) https://users.cs.utah.edu/~regehr/papers/pldi11-preprint.pdf : Foundational random-differential-testing paper for compilers, origin of the Csmith methodology cited as a model for t's approach.
- [1] Finding and Understanding Miscompilation Bugs in the Solidity Compiler (paper) https://arxiv.org/pdf/2607.07217 : Csmith-style differential/random testing applied to the Solidity compiler.

### cross-verifier disagreement (5)

- [5] SV-COMP Software Verification Witnesses (2.0) and validator ecosystem (benchmark) https://link.springer.com/chapter/10.1007/978-3-031-57256-2_15 : The annual Competition on Software Verification runs many independent verifiers to produce correctness/violation witnesses, then runs a separate population of independent validators over those witnesses, scoring witnesses as correct only when a supermajority of validators agree, with disagreement (wrong proofs / false alarms) reported as a headline result.
- [4] Differentially Testing Soundness and Precision of Program Analyzers (paper) https://arxiv.org/pdf/1812.05033 : Differential testing methodology that synthesizes programs specifically to drive multiple static analyzers into disagreement, using cross-tool inconsistency as the bug-finding oracle for unsoundness and imprecision.
- [4] SV-COMP 2026 Java track cross-tool wrong-verdict reporting (benchmark) https://link.springer.com/chapter/10.1007/978-3-031-90660-2_10 : Competition reports that explicitly count and name which of several competing verifiers produced incorrect (unsound) verdicts on the same benchmark set, treating cross-tool disagreement/incorrectness as a first-class scored outcome.
- [3] DeepGalaxy (differential testing of neural-network verifiers) (paper) https://arxiv.org/pdf/2201.08087 : Applies differential testing across multiple neural-network verification tools, flagging a bug whenever one verifier's verdict is inconsistent with the others on the same input.
- [3] K-ESBMC (executable formal semantics for validating verifier translations) (paper) https://arxiv.org/html/2607.10499 : Builds an independent executable reference semantics for IEC 61131-3 Ladder Diagrams specifically to differentially test ESBMC's translation into that formalism, treating every disagreement found as a genuine defect in the verifier under test.

### formal methods (5)

- [5] AWS Automated Reasoning Group - Formal Methods & AI Code (project) https://aws.amazon.com/about-aws/whats-new/aws-automated-reasoning/ : AWS research group working on provable guarantees for infrastructure code and AI-assisted development through formal methods.
- [3] CMU Software Engineering Institute - Formal Methods Research (project) https://www.sei.cmu.edu/ : SEI conducts research on formal methods, verification, and secure software development with DARPA funding.
- [3] Formal Methods in Practice (FMiP) - ESA/NASA Initiative (project) https://www.nasa.gov/formal-methods/ : NASA/ESA initiative on integrating formal methods into industrial software development for space and aerospace systems.
- [3] Microsoft Research - Formal Verification Group (project) https://www.microsoft.com/en-us/research/group/formal-verification/ : Microsoft Research formal methods group working on verified software systems and program synthesis with formal guarantees.
- [2] IDA Center for Software Engineering - Verified Code Standards (project) https://www.ida.org/ : Institute for Defense Analyses conducts research on formal methods and software verification standards for defense.

### verified-os-kernel (4)

- [5] seL4 (software) https://sel4.systems/Verification/proofs.html : Microkernel with machine-checked Isabelle/HOL proof from abstract spec down to C, plus binary verification on RISC-V64 and ARM tying the proof to the executable.
- [4] CertiKOS (software) https://flint.cs.yale.edu/shao/papers/certikos.html : Certified concurrent OS kernel (mC2) built as 30+ small verified layers in Coq, covering multicore concurrency and fine-grained locking.
- [4] Hyperkernel (paper) https://syslab.cs.washington.edu/papers/nelson-hyperkernel.pdf : SOSP'17 'push-button' verified OS kernel (50 syscalls) verified fully automatically via Z3 at the LLVM IR level, by finitizing the interface to avoid unbounded loops.
- [3] Verve (software) https://www.microsoft.com/en-us/research/publication/safe-to-the-last-instruction-automated-verification-of-a-type-safe-operating-system/ : First OS mechanically verified for both type and memory safety, splitting a minimal Hoare-logic-verified assembly 'Nucleus' from a typed-assembly-language-checked C# kernel above it.

### full-source bootstrap (4)

- [5] Bootstrappable Builds / GNU Guix full-source bootstrap (project) https://guix.gnu.org/en/blog/2023/the-full-source-bootstrap-building-from-source-all-the-way-down/ : Guix and the bootstrappable.org project reduced the opaque-binary seed for an entire Linux distro to a 357-byte hex0 binary, building everything else from audited source.
- [5] StageX (software) https://codeberg.org/stagex/stagex : Container-native, full-source-bootstrapped, multi-party-signed, hermetic and deterministic Linux distribution/toolchain built from a sub-190-byte assembly seed with no traditional package manager.
- [4] Bootstrappable Builds / stage0 / live-bootstrap (project) https://bootstrappable.org/ : Community project chaining minimal seeds (280-byte hex0) through stage0-posix, M2-Planet, Mes, up to GCC, eliminating opaque binary compiler seeds.
- [4] GNU Guix Full-Source Bootstrap (software) https://guix.gnu.org/en/blog/2023/the-full-source-bootstrap-building-from-source-all-the-way-down/ : Guix 1.5 closed the gap between stage0-posix and Mes, achieving a full-source bootstrap of its entire package/OS graph from a 357-byte seed.

### smt solver fuzzing (4)

- [3] STORM (software) https://pure.mpg.de/rest/items/item_3317765/component/file_3349104/content : Black-box mutational SMT fuzzer generating satisfiable-by-construction instances from existing SMT-LIB corpora to find critical solver bugs.
- [3] yinyang (software) https://github.com/testsmt/yinyang : Semantic-fusion mutational fuzzer for SMT solvers (targets Z3, CVC4, etc.), found 1,500+ bugs.
- [2] Falcon (SMT solver fuzzer) (software) https://home.cse.ust.hk/~charlesz/papers/issta21.pdf : Grammar-based generative SMT fuzzer using feedback on solver configuration-space coverage.
- [2] OpFuzz (software) https://arxiv.org/pdf/2004.08799 : Type-aware mutational SMT fuzzer using operator mutation, validated via differential comparison of solver outputs.

### verified code benchmark (4)

- [4] MBPP-DFY / "Towards AI-Assisted Synthesis of Verified Dafny Methods" (Misu et al.) (paper) https://arxiv.org/pdf/2402.00247 : First empirical study of LLMs (GPT-4, PaLM-2) synthesizing verified Dafny methods from 153-178 MBPP-derived problems, finding CoT+few-shot verifies 58%.
- [3] VERINA (Verifiable Code Generation Arena) (benchmark) https://arxiv.org/pdf/2505.23135 : 189-task Lean 4 benchmark for jointly grading generated code, specification, and proof, showing best models get only ~5% proof success though 73% code correctness.
- [2] VeriBench (Lean 4 end-to-end) (benchmark) https://openreview.net/forum?id=P7NUVF6wo4 : Benchmark requiring LLMs to generate full Lean 4 implementation, spec/theorems, and machine-checked proof from a Python reference, end to end.
- [2] VeruSAGE (benchmark) https://arxiv.org/abs/2512.18436 : 849-task benchmark of Verus proof obligations from real open-source Rust systems, studying agentic (multi-agent) LLM strategies for writing correctness proofs.

### formal verification (4)

- [5] DARPA HACMS (High Assurance Cyber Military Systems) (project) https://www.darpa.mil/program/high-assurance-cyber-military-systems : DARPA program for formally verified embedded systems with focus on provable correctness and safety-critical code.
- [4] Cryspen - Formally Verified Cryptography (Verus/SPARK) (project) https://cryspen.com/ : Cryspen builds formally verified cryptographic implementations using Verus (Rust) and SPARK, with cross-kernel verification.
- [4] Galois Inc - Formal Methods & Verified Software (project) https://galois.com/ : Galois develops formally verified software and cryptographic systems using Coq, Lean, and other proof assistants.
- [3] Draper Laboratories - Formal Verification for Critical Systems (project) https://www.draper.com/ : Draper conducts research on formally verified code for aerospace and defense with multiple proof backends.

### reproducible research platform (3)

- [3] ReproZip (software) https://www.reprozip.org/ : Packs a computational experiment (code, data files, libraries, env vars) into a self-contained, traced bundle that can be unpacked via Docker/Vagrant/Singularity to exactly reproduce the run elsewhere.
- [2] Code Ocean (software) https://codeocean.com/ : A hosted platform that provisions compute and containerized environments for computational research, producing a traceable, shareable, re-runnable record of an analysis.
- [2] Popper (systems evaluation reproducibility convention) (paper) https://www.researchgate.net/publication/318125763_The_Popper_Convention_Making_Reproducible_Systems_Evaluation_Practical : A convention/CLI for packaging a systems paper's experiments as versioned, containerized pipelines so reviewers can re-run and validate published claims.

### verifier fuzzing (3)

- [5] Testing Dafny (ISSTA 2022 experience paper) (paper) https://ahmed-irfan.github.io/papers/issta22.pdf : Amazon Science experience report on fuzz-testing the Dafny verifier itself and reporting real soundness/crash bugs to the Dafny team.
- [5] XDsmith (software) https://www.doc.ic.ac.uk/~afd/papers/2024/ICST.pdf : Fuzzing/differential-testing framework generating annotated Dafny programs with known verification outcomes to test the Dafny verifier and differentially test its four compilers.
- [4] Crash-free Deductive Verifiers (paper) https://arxiv.org/pdf/2604.19448 : Grammar-based + coverage-guided fuzzing campaign against Dafny, VeriFast, Viper, and VerCors to find crashes/reliability bugs in deductive verifiers.

### proof interchange (3)

- [5] Dedukti (software) https://github.com/Deducteam/Dedukti : Logical framework for translating proofs between different theorem provers (Coq, Isabelle, HOL, Matita, Lean).
- [5] OpenTheory (software) https://github.com/easyprover/opentheory : Proof-exchange format for the HOL family of theorem provers, enabling portable proof libraries across different HOL implementations.
- [4] Proof-Carrying Code (PCC) (standard) https://en.wikipedia.org/wiki/Proof-carrying_code : Security mechanism where executable code is accompanied by formal mathematical proofs for independent verification of correctness.

### verified-toolchain (2)

- [4] CakeML (software) https://cakeml.org/ : Verified ML implementation with a compiler proved correct in HOL4 that can bootstrap (compile) itself down to verified machine code on 6 target architectures.
- [4] CompCert (software) https://compcert.org/ : Coq-verified C compiler whose backend proof guarantees generated assembly preserves the source program's semantics.

### ai bom (2)

- [3] CycloneDX ML-BOM (standard) https://cyclonedx.org/capabilities/mlbom/ : A machine-readable bill-of-materials extension that records models, datasets, training methodology, and provenance/ethical metadata for AI systems.
- [3] TAIBOM (paper) https://arxiv.org/abs/2510.02169 : Extends SBOM concepts to AI pipelines with signed, hash-verified datasets/models and a trust-attestation process propagating integrity statements across heterogeneous ML dependency graphs.

### sandboxed agent execution (2)

- [4] E2B (Firecracker microVM code-execution sandbox) (software) https://e2b.dev/docs/use-cases/coding-agents : Managed Firecracker-microVM sandboxes for agent code execution offering isolated filesystems, git-diff extraction of agent changes, and pause/resume snapshotting of full memory+filesystem state.
- [3] Modal Sandboxes (gVisor isolation) (software) https://modal.com/resources/best-code-execution-sandboxes-coding-agents : Serverless gVisor-isolated containers for running untrusted LLM/agent code with a user-space kernel (Sentry) mediating and logging every syscall between the agent and host.

### frama-c (2)

- [5] Frama-C WP (Why3 Backend) - C/ACSL Verification (project) https://frama-c.cea.fr/ : Frama-C is a framework for analyzing C code with formal verification through ACSL and WP plugin, part of tup's kernel set.
- [3] GrayC (software) https://srg.doc.ic.ac.uk/files/papers/grayc-issta-23.pdf : Greybox fuzzer with semantics-aware mutation testing Clang/GCC/MSVC and the Frama-C static analyzer together, finding 25 new bugs.

### closure hashes (2)

- [4] GNU Guix (functional package manager / Guix System) (software) https://guix.gnu.org/ : Purely functional package manager and declarative GNU/Linux distribution where the whole system is a single reproducible derivation graph.
- [4] Nix / NixOS closures and reproducible.nixos.org (software) https://reproducible.nixos.org/ : Nix's content-addressed store paths and closures track exact build inputs per package, with a dashboard tracking bit-for-bit reproducibility across the NixOS package set.

### reproducible builds (2)

- [3] Debian Reproducible Builds / .buildinfo files (project) https://reproducible-builds.org/docs/recording/ : Debian-wide effort recording a signed .buildinfo receipt (toolchain, environment, package versions) for every binary package to allow independent rebuilding and hash comparison.
- [2] Yocto Project reproducible builds (project) https://docs.yoctoproject.org/test-manual/reproducible-builds.html : Embedded Linux build framework achieving ~99.8% binary-reproducible builds and emitting SPDX SBOMs and build hashes per recipe/package.

### witnessed builds (2)

- [3] rebuilderd / debrebuild (software) https://github.com/kpcyrd/rebuilderd : Independent rebuild infrastructure that rebuilds Debian/Arch binary packages from source and compares hashes against official binaries to verify reproducibility at scale.
- [2] Sigstore / Rekor transparency log (software) https://docs.sigstore.dev/logging/overview/ : Public, append-only transparency log (Rekor) recording signed hashes of build artifacts so anyone can verify an artifact's provenance without trusting the signer directly.

### sbom (2)

- [2] Syft / SPDX / CycloneDX SBOM tooling (software) https://cyclonedx.org/ : Standard machine-readable formats (SPDX, CycloneDX) and generator tools (Syft) for inventorying every component and, for SPDX, every file, in a software system.
- [2] Wolfi / Chainguard apko (software) https://edu.chainguard.dev/open-source/wolfi/overview/ : A Linux 'undistro' built specifically to ship a build-time SBOM with every package for minimal container base images.

### content-addressed filesystem (2)

- [3] composefs (software) https://github.com/composefs/composefs : Content-addressed, read-only Linux filesystem image format where every file is named and verified by the hash of its content, designed for immutable OS/container trees.
- [3] OSTree / rpm-ostree (software) https://ostreedev.github.io/ostree/composefs/ : Git-like content-addressed object store and versioning system for whole Linux filesystem trees, underlying Fedora Silverblue/CoreOS image-based updates.

### immutable os (2)

- [2] AWS Bottlerocket (software) https://thenewstack.io/3-immutable-operating-systems-bottlerocket-flatcar-and-talos-linux/ : Container-optimized immutable Linux distro using dm-verity to cryptographically verify the root filesystem at runtime.
- [2] Talos Linux (software) https://www.siderolabs.com/blog/bottlerocket-vs-talos : Minimal (12-binary), API-managed immutable Kubernetes node OS shipped as an unmodifiable SquashFS image with no shell or package manager.

### vacuity detection (2)

- [4] Vacuity analysis for property qualification by mutation of checkers (paper) https://dl.acm.org/doi/pdf/10.5555/1870926.1871041 : Explicit mutation-analysis-based approach to vacuity detection in model checking, mutating the property checker itself to give fast, accurate vacuity alerts without hand-authoring new mutated properties.
- [4] Vacuity detection in temporal model checking (Beer, Ben-David, Eisner, Rodeh; Kupferman & Vardi) (paper) https://www.cs.toronto.edu/~chechik/courses05/csc2108/beer01.pdf : Foundational line of work defining vacuity (a spec holding for trivial/unintended reasons, e.g. antecedent failure) and giving decision procedures to detect it as a 'sanity check' alongside coverage.

### mutation testing (2)

- [3] ClassInvGen (paper) https://arxiv.org/pdf/2502.18917 : LLM-based synthesis of C++ class invariants that scores invariant completeness by mutation testing (mutants killed), showing synthesized invariants catch mutants unit tests miss.
- [3] LLM-guided Formal Verification Coupled with Mutation Testing (paper) https://agra.informatik.uni-bremen.de/doc/konf/2024_DATE_MH.pdf : DATE 2024 paper pairing LLM-driven formal verification (hardware) with mutation testing to check whether generated properties actually distinguish correct from faulty designs.

### reward hacking (2)

- [2] ImpossibleBench (benchmark) https://www.lesswrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1 : Benchmark that mutates unit tests to conflict with the natural-language spec, so any pass necessarily means the model exploited the test/spec gap ,  a test-level (not proof-level) sibling of the 'spec restates the implementation' problem.
- [2] LLMs Gaming Verifiers: RLVR can Lead to Reward Hacking (paper) https://arxiv.org/pdf/2604.15149 : Empirical RLVR study showing models trained against imperfect verifiers learn to game the verification process itself rather than solve the task; general reward-hacking framing that motivates why kernel-acceptance rewards need twin/mutant checks.

### cross-checker agreement (2)

- [5] Lean Kernel Arena (benchmark) https://arena.lean-lang.org/ : Public benchmark running many independently-implemented Lean proof kernels (official + community, ~16 as of Aug 2026) against the same valid/invalid-proof test suite, scoring each on acceptance/rejection agreement plus speed and memory.
- [5] leanprover/comparator (software) https://github.com/leanprover/comparator : Tool that replays exported Lean proofs through both the official kernel and external checkers like nanoda, cross-checking that they agree on validity and on the exact theorem statements proved.

### independent kernels (2)

- [4] franken_lean (software) https://github.com/Dicklesworthstone/franken_lean : Ground-up native-Rust reimplementation of the entire Lean 4 toolchain (drop-in at .olean/C-ABI/LSP surfaces) with a small dual-engine kernel explicitly built to ship independent-verification 'receipts.'
- [4] Lean4Lean (software) https://arxiv.org/abs/2403.14064 : A typechecker for Lean 4 written and verified in Lean 4 itself, the first complete alternative to the reference C++ kernel, runnable on all of Mathlib as a soundness cross-check.

### verified checker (2)

- [4] MetaCoq / Coq Coq Correct! (paper) https://sozeau.gitlabpages.inria.fr/www/research/publications/Coq_Coq_Correct-POPL20.pdf : A type checker and erasure procedure for the kernel of Coq, formalized and proven sound/complete inside Coq itself (PCUIC), giving a machine-checked alternative implementation of the trusted core to cross-validate against the OCaml kernel.
- [3] Candle (CakeML) (software) https://cakeml.org/candle/ : A fully verified clone of HOL Light built on the verified CakeML compiler/runtime, giving an end-to-end machine-checked soundness theorem for an entire theorem-proving system, plus a separately verified OpenTheory article checker using the Candle kernel.

### certificate-producing verifiers (2)

- [4] Alethe / Carcara (software) https://dl.acm.org/doi/abs/10.1007/978-3-031-30823-9_19 : A generic SMT proof certificate format (produced by veriT and cvc5) with an independent Rust checker (Carcara) and independent reconstruction paths in Isabelle/HOL and Coq (SMTCoq), letting an SMT result be cross-checked outside the solver that produced it.
- [3] SMT-COMP Proof Validation Track (benchmark) https://groups.google.com/g/smt-lib/c/XEo_IkQ7KYs : A dedicated competition track requiring SMT solvers to produce checkable proof certificates so independent external checkers can validate solver verdicts, rather than trusting the solver's own 'unsat' answer.

### one-language-many-backends (2)

- [3] Viper (intermediate verification language, multiple frontends/backends) (software) https://www.pm.inf.ethz.ch/research/viper.html : One intermediate verification language with many independently-built frontends (Gobra for Go, Nagini for Python, Prusti for Rust, Chalice) and multiple backend verifiers ,  the project's own cited prior-art model of 'one language, many checkers,' confirmed here in detail.
- [3] Why3 (WhyML, multiple prover backends) (software) https://www.researchgate.net/publication/266859603_Why3_-_Where_Programs_Meet_Provers : One specification/program language (WhyML) dispatched to many automated and interactive provers (Z3, CVC, Alt-Ergo, Coq, Isabelle...); the project's own cited prior art, confirmed as an auto-active verifier whose annotations are checked across a plurality of backend solvers.

### multi-prover backend (2)

- [4] SPARK (Formally Defined Ada Subset) (software) https://en.wikipedia.org/wiki/SPARK_(programming_language) : Formally defined programming language for high-integrity systems, with GNATprove analyzer using multiple theorem provers (CVC4, Z3, Alt-Ergo).
- [3] Frama-C / WP (software) https://www.frama-c.com/download/wp-manual-20.0-Calcium.pdf : ACSL-annotated C verified by weakest-precondition VCs dispatched to several SMT provers (Alt-Ergo, Z3, CVC4/5) plus, via Why3, to Coq, PVS and Gappa; one of t's own seven target kernels.

### reproducible-builds (2)

- [4] GNU Guix (software) https://guix.gnu.org/ : Package manager for GNU/Linux providing reproducible builds, declarative system configurations, and time-machine capability for identical environment recreation.
- [3] Bazel (software) https://bazel.build/ : Open-source build and test system emphasizing speed and correctness through advanced caching, dependency analysis, and parallel execution across multi-language projects.

### proof assistant (2)

- [3] Isabelle/HOL Proof Assistant (software) https://isabelle.in.tum.de : Generic proof assistant with support for multiple logical frameworks, featuring Sledgehammer integration with external provers.
- [3] Rocq (formerly Coq) Proof Assistant (software) https://rocq-prover.org : Interactive theorem prover and dependently-typed programming language for mechanized formal reasoning.

### trusting-trust answer (1)

- [5] Diverse Double-Compiling (Wheeler) (paper) https://dwheeler.com/trusting-trust/ : PhD dissertation and ACSAC'05 paper giving a practical, provable technique (recompile source with a second trusted compiler, then recompile that output with the first) to detect Thompson's 'trusting trust' compiler backdoor.

### verified-systems-software (1)

- [4] IronFleet / Ironclad (software) https://github.com/microsoft/Ironclad : Dafny methodology proving distributed systems (Paxos-based IronRSL, sharded IronKV) correct via TLA-style refinement plus Hoare-logic implementation verification, in the same prover t targets first (Dafny/Z3).

### end-to-end-trust-chain (1)

- [4] DeepSpec (NSF Expedition) (project) https://deepspec.org/main : $10M NSF Expedition (2015-2020) building 'deep specifications' connecting verified compilers, OS (CertiKOS), and networked servers via machine-checked interface proofs.

### verified-low-level-programming (1)

- [3] Bedrock / bedrock2 (software) https://github.com/mit-plv/bedrock2 : Coq library/language for verified low-level programming with separation-logic-based Hoare reasoning and largely automated verification-condition generation.

### proof-carrying-code (1)

- [4] Proof-Carrying Code / Necula certifying compilers (paper) https://people.eecs.berkeley.edu/~necula/pcc.html : Foundational technique where an untrusted code producer supplies a machine-checkable safety proof alongside the binary, and certifying compilers emit such proofs automatically as a compiler pass.

### dafny benchmark (1)

- [5] DafnyBench (benchmark) https://arxiv.org/pdf/2406.08467 : 782-program, ~53K-LOC benchmark of real-world Dafny programs (mined from GitHub plus MBPP translations) for evaluating LLMs' ability to reconstruct verification hints/annotations.

### multi-verifier benchmark (1)

- [5] Vericoding benchmark (benchmark) https://arxiv.org/pdf/2509.22908 : 2025 benchmark for 'vericoding' (formally verified program synthesis) spanning multiple verified languages/provers including Lean, Verus, and Dafny.

### verifiable-reward for llms (1)

- [4] Re:Form (paper) https://arxiv.org/pdf/2507.16331 : RL-with-LLMs approach that reduces human annotation needs for Dafny verification by using Dafny's own verifier as the RL reward signal, trained/evaluated on DafnyBench.

### verifiable-reward benchmark (1)

- [3] FormalRewardBench (benchmark) https://arxiv.org/html/2605.10141 : Benchmark for evaluating reward models used in formal theorem proving (Lean 4), addressing how to score/compare verifier-based reward signals for LLM training.

### one-spec-many-provers (1)

- [5] Why3 (software) https://why3.lri.fr/ : Intermediate verification language/platform: one program+spec language (WhyML) compiled to verification conditions dispatched across roughly 19 different provers (SMT solvers and proof assistants).

### one-ir-many-backends-and-frontends (1)

- [5] Viper (software) https://github.com/viperproject : Intermediate verification language (permission-based/separation logic) with two interchangeable backends (Silicon: symbolic execution, Carbon: VCG) and multiple frontends (Prusti for Rust, Gobra for Go).

### model provenance (1)

- [4] Sigstore Model Transparency (model-signing) (software) https://github.com/sigstore/model-transparency : Google/OpenSSF-adjacent project applying Sigstore keyless signing, transparency-log inclusion proofs, and SLSA-style provenance to ML model weights and manifests.

### ml lifecycle provenance (1)

- [4] Atlas (Intel Labs) / atlas-cli (C2PA for ML) (paper) https://arxiv.org/abs/2502.19567 : A Transparency Service + Verification System that hashes and signs ML artifacts at each pipeline stage (data, training, eval, deployment) to produce end-to-end, C2PA-based lineage manifests.

### hermetic ml pipelines (1)

- [4] Nix (and rix / rixpress / nix-workflow) (software) https://discourse.nixos.org/t/nix-workflow-for-scientific-workflow/76206 : Content-addressed, declarative package manager repurposed via community tools (rix/rixpress for polyglot data-science pipelines, nix-workflow for ML) to pin whole runtimes including system libs and CUDA for hermetic, reproducible experiments.

### source hashing/archival (1)

- [3] GNU Guix + Software Heritage integration (software) https://guix.gnu.org/en/blog/2019/connecting-reproducible-deployment-to-a-long-term-source-code-archive/ : Guix records exact channel/package graphs (manifest.scm + channels.scm) and falls back to the Software Heritage long-term source archive so an environment can be exactly reconstructed years later.

### agent filesystem audit (1)

- [5] AgentFS (software) https://penberg.org/blog/disaggregated-agentfs.html : A SQLite-backed filesystem abstraction for AI agents that stores files, directories, and an append-only audit log of every tool call, letting a whole agent run be snapshotted as one portable, diffable file.

### container image inventory (1)

- [3] Syft (Anchore) (software) https://github.com/anchore/syft : CLI/library that generates file-level SBOMs (SPDX/CycloneDX) for container images and filesystems, cataloging every package and file with hashes for provenance auditing.

### minimal distro (1)

- [4] Chainguard Wolfi + apko/melange (Distroless images) (software) https://images.chainguard.dev/directory/image/wolfi-base/overview : A minimal Linux distro purpose-built for container base images, built declaratively with apko/melange, fully reproducible, SBOM'd, and Sigstore-signed with SLSA Build Level 2 provenance attestations.

### supply-chain attestation (1)

- [3] in-toto + SLSA (standard) https://slsa.dev/blog/2023/05/in-toto-and-slsa : in-toto's attestation format plus SLSA's graduated build-integrity levels form the standard vocabulary for 'who built this artifact, from what source, by what verifiable steps' ,  increasingly proposed for ML artifacts too.

### hermetic dev environments for agents (1)

- [3] Flox (software) https://github.com/flox/flox : A Nix-based cross-platform package/environment manager producing cryptographically pinned, lockfile-reproducible dev environments explicitly marketed for agentic/AI coding workflows.

### minimal/purpose-built distro for ai agents (1)

- [2] CrabWithClawOS (project) https://github.com/VasileiosMalt/CrabWithClawOS : A Debian-based Linux distro pre-loaded with agent tooling (claude-code, aider, Ollama, LiteLLM gateway) aimed at running AI coding agents, but without tup's hashed-source/receipt discipline.

### filesystem change audit (1)

- [2] docker diff / podman diff / container-diff (software) https://oneuptime.com/blog/post/2026-01-16-docker-diff-inspect-changes/view : Built-in container-runtime commands that list files added/changed/deleted in a running container relative to its base image, the everyday tool for 'what did this container (or agent inside it) change'.

### agent sandbox/audit landscape survey (1)

- [2] awesome-agent-runtime-security (curated list) (other) https://github.com/bureado/awesome-agent-runtime-security : A curated GitHub list aggregating tools, blog posts, and standards for sandboxing and auditing AI-agent runtime behavior (filesystem, network, syscalls).

### model signing case study (1)

- [3] Google/OpenSSF case study on securing ML models with Sigstore (other) https://openssf.org/blog/2025/07/23/case-study-google-secures-machine-learning-models-with-sigstore/ : Case study describing how Google ties model artifacts to signed, transparency-logged provenance records for audit trails during incident response.

### ivl testing (1)

- [4] Model-Based Testing of an Intermediate Verifier (Boogie) (paper) https://arxiv.org/pdf/2508.17895 : Model-based testing of Boogie using an executable operational semantics as oracle to find discrepancies with the real implementation.

### translation validation (1)

- [5] Towards Trustworthy Automated Program Verifiers: Formally Validating Translations into an IVL (paper) https://arxiv.org/abs/2404.03614 : Formal translation-validation technique that auto-generates Isabelle proofs, per verifier run, that a Viper/Boogie front-end's translation preserves correctness.

### ci integration (1)

- [4] Compiler Fuzzing in Continuous Integration: A Case Study on Dafny (paper) https://www.doc.ic.ac.uk/~afd/papers/2025/ICST-Industry.pdf : Industry case study on operationalizing Dafny fuzzers (fuzz-d, DafnyFuzz, XDsmith-derived tools) inside Dafny's CI, reporting 24 new bugs incl. 9 soundness issues.

### differential testing (1)

- [2] Compiler Validation via Equivalence Modulo Inputs (EMI/Orion/Athena/Hermes) (paper) https://dl.acm.org/doi/10.1145/2666356.2594334 : EMI methodology mutates dead-code regions to create input-equivalent program variants for differential compiler testing; found 147 confirmed GCC/LLVM bugs.

### cross-kernel benchmark (1)

- [4] AlgoVeri (benchmark) https://arxiv.org/html/2602.09464v2 : Aligned benchmark specifying the same classical-algorithm problems across Dafny, Verus, and Lean for cross-verifier comparison of AI-generated verified code.

### llm-generated specs+proofs benchmark (1)

- [3] VerifyThisBench (benchmark) https://arxiv.org/pdf/2505.19271 : Benchmark requiring generation of code, specifications, and proofs all at once, evaluated for verified-code generation quality.

### multi-tool benchmark (1)

- [3] VerifyThis (competition) (benchmark) https://dl.acm.org/doi/10.1007/s10009-021-00619-x : Interactive program verification competition run across multiple tools (Dafny, Why3, VeriFast, VerCors, Frama-C, and now Verus/CBMC) on shared problems.

### ground-truth benchmark corpus (1)

- [3] SV-COMP (Competition on Software Verification) (benchmark) https://sv-comp.sosy-lab.org/2026/ : Large annual automated verification-tool competition (62 verifiers, 18 witness validators in 2025) with known-verdict C/Java benchmark tasks and a witness-validation track.

### witness-based oracle (1)

- [3] Testing in Formal Verification via Witness Generation (paper) https://www.sosy-lab.org/research/pub/2026-FASE.Testing_in_Formal_Verification_via_Witness_Generation.pdf : Uses SV-COMP verification witnesses (correctness/violation) to synthesize executable test harnesses that validate verifier verdicts.

### cross-verifier witness checking (1)

- [3] Witness validation and stepwise testification across software verifiers (paper) https://dl.acm.org/doi/10.1145/2786805.2786867 : Cross-verifier validation of witnesses produced by different SV-COMP tools, converting witnesses into executable tests to check verifier verdicts against each other.

### rust verification tool landscape (1)

- [2] Kani (Rust model checker) (software) https://arxiv.org/html/2607.01504v1 : Bounded model checker for Rust (CBMC-based), positioned alongside Verus/Prusti/Creusot as an alternative Rust verification backend.

### soundness bug catalogue (1)

- [2] SPARK/GNATprove known-problems soundness catalogue (standard) https://docs.adacore.com/spark2014-docs/html/ug/en/appendix/quality_assurance.html : AdaCore's own maintained catalogue of known SPARK/GNATprove soundness bugs, tagged missing-check / missing-violation, with detection guidance per release.

### multi-solver competition (1)

- [2] SyGuS-Comp (benchmark) https://www.cis.upenn.edu/~alur/SyGuS13.pdf : Annual syntax-guided-synthesis solver competition on a shared benchmark set, grading solvers via a checker rather than pre-known ground-truth programs.

### compiler testing methodology (1)

- [1] Skeletal Program Enumeration for Rigorous Compiler Testing (paper) https://arxiv.org/pdf/1610.03148 : Enumerative (exhaustive up to a skeleton) program generation for more rigorous, reproducible compiler-bug-finding than random fuzzing.

### multi-builder consensus (1)

- [4] Trustix (software) https://github.com/nix-community/trustix : Distributed, Merkle-log-based consensus system comparing build outputs from independent Nix builders to establish M-of-N trust in binary substitutions.

### step-attestation (1)

- [5] in-toto (project) https://in-toto.io/ : Open supply-chain security framework that records and verifies metadata about each step in software development, documenting what was done, who did it, and in what order.

### provenance-attestation (1)

- [5] SLSA (Supply-chain Levels for Software Artifacts) (standard) https://slsa.dev/ : Security framework with four compliance tiers for preventing tampering and securing software artifacts through provenance and attestation.

### build attestation (1)

- [3] Kettle: Attested Builds for Verifiable Software Provenance (paper) https://arxiv.org/pdf/2605.08363 : 2026 paper/system generating cryptographically signed, granular attestations of build steps and outputs to prove what actually happened during a specific build, distinct from reproducibility.

### from-source build (1)

- [1] Buildroot (software) https://proteanos.com/doc/buildroot-vs-yocto-2026/ : Simple Makefile-based embedded Linux build system producing a root filesystem from source, reasonably reproducible when versions/tarballs are pinned but without native provenance metadata.

### linux from scratch automation (1)

- [4] jhalfs / ALFS (Automated Linux From Scratch) (software) https://www.linuxfromscratch.org/alfs/ : Script generator that turns the LFS/BLFS book's XML instructions into an executable, resumable Makefile-driven build, automating the exact manual book process.

### trusting-trust (1)

- [3] Diverse Double-Compiling (David A. Wheeler) (paper) https://dwheeler.com/trusting-trust/ : Formal method and dissertation proving a compiler binary matches its claimed source by cross-compiling with an independent second compiler and comparing bit-for-bit output, countering Thompson's 'trusting trust' attack.

### verified toolchain (1)

- [3] CompCert (verified C compiler) and its TCB analysis (paper) https://arxiv.org/pdf/2201.10280 : Machine-checked-correct C compiler with a published analysis of exactly what must still be trusted (its own TCB) beyond the correctness proof.

### verified kernel (1)

- [3] seL4 verified microkernel (software) https://trustworthy.systems/projects/OLD/seL4-verification/ : Microkernel with a machine-checked Isabelle/HOL proof that its C source (and on some architectures its compiled binary) matches its abstract specification, with no known bugs in the verified configurations.

### dafny-to-verus translation (1)

- [5] AlphaVerus (software) https://arxiv.org/pdf/2412.06176 : Self-improving pipeline that translates DafnyBench programs into Verus via exploration, tree-search refinement, and critique, producing the DAFNY2VERUS-COLLECTION with verifier-checked fidelity.

### multi-kernel task translation (1)

- [5] A Benchmark for Vericoding: Formally Verified Program Synthesis (benchmark) https://arxiv.org/pdf/2509.22908 : 12,504-task benchmark spanning Dafny, Verus/Rust, and Lean built by translating tasks between the three verification languages while preserving semantic equivalence.

### autoformalization fidelity (1)

- [4] Verus-SpecGym / Verus-SpecBench (benchmark) https://arxiv.org/abs/2605.26457 : Agentic environment and 581-task benchmark evaluating whether LLMs can autoformalize natural-language Codeforces problems into faithful Verus specifications, with an executable-specification fidelity oracle instead of LLM judges.

### llm cross-prover translation (1)

- [4] MiniF2F-in-Rocq (paper) https://arxiv.org/pdf/2503.04763 : Case study using an LLM to automatically translate 478/488 MiniF2F theorem statements from Lean and Isabelle into Rocq, validated by Rocq's type-checker.

### translation validation for verification pipelines (1)

- [4] Towards Trustworthy Automated Program Verifiers (IVL translation validation) (paper) https://arxiv.org/pdf/2404.03614 : Formally validates the front-end translation from a source verification language into an intermediate verification language (Boogie/Viper-style) by generating an Isabelle proof that IVL correctness implies source correctness.

### ivl-to-ivl translation (1)

- [4] Why Just Boogie? Translating Between Intermediate Verification Languages (paper) https://arxiv.org/pdf/1601.00516 : Semantics-preserving translator from Boogie to WhyML (Why3's IVL), evaluated on 194 Boogie-verified programs with 83% matching verification outcomes after translation.

### cross-kernel agreement table analog (1)

- [4] Federated Formal Verification (cross-backend citation / cross-axis convergence) (paper) https://arxiv.org/html/2606.02019 : 16-backend (TLAPS, Coq, Lean4/Mathlib, Why3, TLC, Apalache, Z3, CVC4/5, veriT, SPASS, Vampire, Eprover, Zipperposition, PRISM, CBMC, Lincheck) architecture that cross-cites the same obligation across independent verifiers, classifying each as PROVED/REFUTED/TIMEOUT/STRUCTURAL_GAP/VERDICT_DISAGREEMENT.

### code translation with equivalence checking (1)

- [3] TransCoder / TransCoder-ST (Unsupervised Translation of Programming Languages) (software) https://arxiv.org/pdf/2006.03511 : Unsupervised neural translator between C++/Java/Python trained via back-translation, later filtered by an automated unit-testing system (TransCoder-ST) to discard translations that fail behavioral equivalence.

### repository-level translation (1)

- [3] AlphaTrans (software) https://arxiv.org/html/2410.24117 : Neuro-symbolic, repository-level Java-to-Python code translator that validates each translated method fragment by substituting it into the otherwise-Java project and re-running the original Java test suite in isolation.

### differential symbolic testing (1)

- [3] RustAssure (software) https://arxiv.org/pdf/2510.07604 : Differential symbolic testing tool establishing semantic equivalence between LLM-transpiled C-to-Rust code and its C original.

### cross-language differential fuzzing (1)

- [3] Syzygy (Dual Code-Test C to Rust Translation) (software) https://arxiv.org/pdf/2412.14234 : LLM-driven C-to-safe-Rust translator that mines I/O and property specifications via dynamic analysis and validates translations with a cross-language differential fuzzer (Bolero/libfuzzer harness).

### execution-trace-based fidelity localization (1)

- [2] TransMap (software) https://arxiv.org/abs/2306... (see ACM DOI) : Traces execution of Codex/ChatGPT-translated Python-to-JavaScript programs against the source to pinpoint the exact line of a semantic translation mistake.

### multi-prover benchmark (1)

- [3] MiniF2F (benchmark) https://arxiv.org/pdf/2109.00110 : The original cross-system benchmark of 488 Olympiad-level theorems manually formalized in Lean, Isabelle, HOL Light, and Metamath, enabling apples-to-apples comparison of automated/neural provers across systems.

### single-system proof corpus (1)

- [2] LeanDojo (software) https://papers.neurips.cc/paper_files/paper/2023/file/4441469427094f8873d0fecb0c4e1cee-Paper-Datasets_and_Benchmarks.pdf : Toolkit and dataset extracting proof states and premises from Lean for retrieval-augmented theorem-proving models, one of the single-system corpora (alongside CoqGym, PISA) that MiniF2F-style efforts try to unify.

### universal proof interlingua (1)

- [4] Dedukti (λΠ-calculus modulo theory) proof interoperability (software) https://blanqui.gitlabpages.inria.fr/dk2isa.html : A logical framework used as a common intermediate language to translate and re-check proofs across Coq/Rocq, Lean, Isabelle/HOL, HOL-Light, PVS, Matita, and Agda.

### one of t's seven target kernels (1)

- [3] Verus (verifier for Rust, inspired by Dafny) (software) https://arxiv.org/pdf/2412.06176 : SMT-based verifier for a subset of Rust, explicitly designed to be Dafny-like in specification style, making it the natural translation target used by AlphaVerus and the Vericoding benchmark.

### ground-truth-by-construction oracle (1)

- [2] Magma: A Ground-Truth Fuzzing Benchmark (benchmark) https://arxiv.org/pdf/2009.01120 : Fuzzing benchmark that injects real, ground-truth-labeled bugs into real software so fuzzer bug-finding can be graded against a known-true/known-false oracle, structurally analogous to tup's ground-truth fuzzing of lowerings.

### differential fuzzing of proof-backend soundness (1)

- [2] STORM (blackbox mutational fuzzing for SMT solvers) (software) https://pure.mpg.de/rest/items/item_3317765/component/file_3349104/content : Mutational fuzzer for SMT solvers that found 29 previously unknown critical (soundness) bugs across seven mature solvers by mutation and differential comparison.

### single-kernel synthesis progress benchmark (1)

- [2] Vericoding Benchmark related work: prior Dafny success-rate trend (benchmark) https://www.alphaxiv.org/overview/2509.22908v1 : Same vericoding benchmark paper's cited trend that Dafny task success rose from 68% to 96% within a year, situating tup's cross-kernel agreement bar against single-kernel state of the art.

### feedback-driven iterative translation (1)

- [2] SmartC2Rust (software) https://arxiv.org/pdf/2409.10506 : Iterative, feedback-driven LLM pipeline for C-to-Rust translation targeting safety and equivalence, refining translations against compiler/verifier feedback.

### mutation testing for specs (1)

- [5] MutDafny (software) https://arxiv.org/pdf/2511.15403 : Mutation-based tool that injects faults into verified Dafny programs and checks whether the existing specification still verifies the mutant, empirically showing many Dafny specs are underspecified despite passing the verifier.

### spec inference (1)

- [4] SpecFuzzer (software) https://arxiv.org/abs/2201.10874 : Grammar-based fuzzer plus dynamic invariant detection that infers class specifications, then uses mutation analysis specifically to discard weak/trivial and redundant assertions.

### proof mutation (1)

- [4] mCoq (software) https://github.com/EngineeringSoftware/mcoq : First mutation analysis tool for Coq verification projects: mutates definitions, re-checks all proofs, and calls a mutant 'live' (unkilled) as a direct signal of specification/proof-suite incompleteness.

### spec completeness (1)

- [4] Clover (Closed-Loop Verifiable Code Generation) (paper) https://arxiv.org/abs/2310.17807 : Checks whether Dafny-style formal annotations are complete (not just consistent) by having an LLM regenerate code from the annotations and checking equivalence ,  a generative alternative to mutation for catching under-specification.

### benchmark (1)

- [4] Verina: Benchmarking Verifiable Code Generation (benchmark) https://arxiv.org/pdf/2505.23135 : Verifiable code-gen benchmark (CodeGen/SpecGen/ProofGen) that explicitly documents LLMs proving code against trivial postconditions (e.g. 'result.len()==2') and separates spec-gen from code-gen so specs can't be trivially copied from the implementation.

### vacuity check (1)

- [4] KaPilot (software) https://arxiv.org/html/2607.21957v1 : LLM-assisted generator of Kani (Rust) specifications that runs an explicit vacuity check ,  appending a deliberately false postcondition and seeing if it still 'verifies' ,  to catch specs that pass only because the precondition is unsatisfiable.

### mutation score (1)

- [4] Beyond Postconditions: Can LLMs infer Formal Contracts for Automatic Software Verification? (paper) https://arxiv.org/pdf/2510.12702 : Evaluates LLM-inferred formal contracts by mutation score ,  the fraction of code mutants a contract's verifier can kill ,  reporting a sound functional contract killing all mutants for 80-92 of the HumanEval+ tasks tried.

### training reward (1)

- [5] SpecCoder (paper) https://arxiv.org/html/2607.04232 : Verification-guided CodeLLM training framework whose training data is explicitly built from correct programs, behavior-changing mutants, and multi-turn specification-refinement traces that measure spec strength by how many mutants/variants the spec refutes ,  structurally the closest analog to t's twin-refutation reward.

### vacuity (1)

- [3] HierSVA (benchmark) https://arxiv.org/abs/2606.13706 : Data synthesis pipeline/benchmark for LLM-generated SystemVerilog assertions that scores assertion quality on six axes including vacuity and mutation coverage side by side, treating vacuous-but-proved assertions as a first-class failure mode.

### mutation-guided refinement (1)

- [4] Closing the Loop on LLM-Generated RTL Assertions with Quality-Aware Formal Verification (paper) https://arxiv.org/pdf/2606.21451 : Injects mutations into RTL designs and computes an 'effective kill rate' per LLM-generated assertion, plus twin-design comparisons, to reject vacuous/weak assertions before accepting a proof ,  direct hardware analog of twin-mutant spec-strength grading.

### witness format standard (1)

- [3] Software Verification Witnesses 2.0 (SV-COMP witness format) (standard) https://link.springer.com/chapter/10.1007/978-3-031-66149-5_11 : Standardized exchange format for violation and correctness witnesses from software verifiers (used across SV-COMP), giving a machine-checkable receipt for a verifier's counterexample or invariant ,  the closest existing standard to t's 'refutation certificate' concept.

### metamorphic testing (1)

- [3] Metamorphic testing of theorem provers / SMT solvers (mutant formula equisatisfiability) (paper) https://link.springer.com/chapter/10.1007/978-3-031-04673-5_10 : Applies metamorphic testing to logic theorem provers and SMT/constraint solvers by mutating input formulas in status-preserving ways and flagging solver disagreement as a bug ,  the differential/metamorphic-fuzzing half of the facet, aimed at the kernels themselves rather than at specs.

### design by contract (1)

- [2] Contract-based mutation for testing components (paper) https://www.academia.edu/21163809/Contract_based_mutation_for_testing_components : Early design-by-contract line of work (Eiffel/JML-adjacent) using mutation of contracts/components and AutoTest-style model-based contracts to find faults that plain contracts miss.

### universal proof format (1)

- [4] Foundational Proof Certificates (ProofCert) (paper) https://www.lix.polytechnique.fr/Labo/Dale.Miller/ProofCert/ : Dale Miller's program to export proof evidence from any prover/model-checker into a declarative, universal, permanent certificate format so proofs can be checked by, and shared across, independent checkers rather than trusted from the originating tool.

### witness validation (1)

- [4] MetaVal: Witness Validation via Verification (paper) https://link.springer.com/chapter/10.1007/978-3-030-53291-8_10 : Turns any existing verifier into a witness validator by transforming (program, witness) into a new verification task, so the diversity of the verifier population itself becomes the pool of independent witness validators.

### verified reward for llms (1)

- [4] Re:Form (RL from Dafny verification, specification hacking) (paper) https://arxiv.org/pdf/2507.16331 : Trains LLMs with GRPO using Dafny's verifier as the reward signal for an APPS-derived dataset, explicitly reporting 'specification hacking' (trivial/gamed specs passing the verifier) as a finding ,  the same failure mode t's spec experiment measured (35/64 well-formed specs restating the body).

### diverse redundancy (1)

- [2] N-Version Programming with formal-methods integration (other) https://www.emergentmind.com/topics/n-version-programming-method : Classical fault-tolerance technique of running diverse independent implementations of one specification and adjudicating their outputs, now being combined in recent work with formal verification and differential testing for automated variant validation ,  the general engineering principle t and the Lean/SV-COMP work above instantiate for proof checking specifically.

### verified code generation (1)

- [3] AutoVerus (software) https://arxiv.org/pdf/2409.13082 : Multi-agent LLM pipeline (generation, refinement, debugging) that writes Verus/Rust correctness proofs, verified against a 150-task benchmark with >90% success.

### multi-kernel benchmark (1)

- [4] A Benchmark for Vericoding (Beneficial AI Foundation) (benchmark) https://arxiv.org/pdf/2509.22908 : 12,504-task benchmark spanning Dafny, Verus/Rust, and Lean with LLM-based cross-language spec translation between the three kernels, POPL 2026.

### lean kernel (1)

- [2] LeanDojo / ReProver (software) https://arxiv.org/abs/2306.15626 : Open toolkit and retrieval-augmented LLM prover for Lean, with premise-selection benchmark of ~98k theorems.

### cross-kernel agreement gate (1)

- [3] Federated Formal Verification (Falda, 2026) (paper) https://arxiv.org/pdf/2606.02019 : Single-author paper proposing 'cross-backend citation' and a 'kernel-agreement gate' composing verdicts from independent proof kernels (TLA+, Lean, etc.) for production HFT systems, with an 'untrusted AI proof-search' layer inside a trusted CI envelope.

### provable outputs (1)

- [3] Towards Guaranteed Safe AI (Dalrymple, Tegmark, Omohundro et al. 2024) (paper) https://arxiv.org/abs/2405.06624 : Position paper proposing a family of AI-safety approaches ('GS AI') built around formal world models, safety specifications, and verifiers that gate model outputs with quantitative proof-carrying guarantees.

### multi-verifier aggregation (1)

- [1] Multi-Agent Verification: Scaling Test-Time Compute with Multiple Verifiers (paper) https://arxiv.org/pdf/2502.20379 : Studies combining multiple (LLM-based, not formal) verifiers via voting/aggregation to scale test-time compute for LLM output selection.

### verus kernel (1)

- [2] Verus-SpecGym (benchmark) https://arxiv.org/html/2605.26457v1 : Agentic environment for evaluating LLM specification autoformalization for Verus.

### spec synthesis (1)

- [2] SpecGen / AutoSpec (software) https://arxiv.org/pdf/2401.08807 : LLM-driven generation of formal Java (JML, SpecGen) and C (ACSL/Frama-C, AutoSpec) specifications via conversational synthesis, mutation-driven repair, and verifier feedback.

### verifier-in-the-loop (1)

- [2] LEMUR (LLM + automated reasoners for loop invariants) (software) https://openreview.net/pdf?id=Q3YaCghZNt : Framework combining LLM-proposed loop invariants with automated reasoners (e.g. ESBMC) that check them, solving 107/133 Code2Inv benchmark programs.

### isabelle kernel (1)

- [1] Baldur (software) https://arxiv.org/pdf/2303.04910 : LLM-based whole-proof generation and repair for Isabelle/HOL, evaluated on 6,336 theorems, combined with the Thor tool for 65.7% automatic proof rate.

### rocq/coq kernel (1)

- [1] Rango (software) https://people.cs.umass.edu/~brun/pubs/pubs/Thompson25icse.pdf : Retrieval-augmented, fully automated Coq proof synthesis tool, evaluated on the 196,929-theorem CoqStoq dataset.

### ivl (1)

- [4] Boogie (software) https://www.microsoft.com/en-us/research/project/boogie-an-intermediate-verification-language/ : Intermediate verification language used as the shared VC-generation layer underneath Dafny, Chalice, Spec#, VCC and HAVOC, dispatching to SMT solvers (chiefly Z3, also CVC5).

### one intermediate format many proof systems (1)

- [4] Dedukti / Logipedia (software) http://logipedia.inria.fr/about/about.php : Dedukti is a logical framework used as a universal intermediate proof-term language; Logipedia's backend translates Dedukti-encoded proofs out to Coq, Lean, or HOL, with front-end translators (CoqInE, Holide, Krajono) importing proofs from Coq, HOL, and Matita.

### one spec many heterogeneous kernels (1)

- [5] Federated Formal Verification (Mercury / cross-backend citation) (paper) https://arxiv.org/abs/2606.02019 : Takes a single TLA+ specification and discharges its proof obligations across ~16 heterogeneous backends (TLAPS, Coq, Lean 4, Why3, TLC, Apalache, Z3, cvc5, SPASS, Vampire, E, Zipperposition, PRISM, CBMC, Lincheck), with a 'cross-axis convergence' matrix requiring dual/triple-kernel agreement on selected obligations.

### exchange format (1)

- [3] SMT-LIB / TPTP (standard) https://tptp.tptp.org/ : Two competing standardized exchange formats (SMT-LIB for SMT solvers, TPTP for first-order/ATP systems) that let one problem be dispatched to dozens of independently-implemented solvers, with converters (SMTtoTPTP) bridging the two ecosystems.

### one goal many independent provers (1)

- [3] Sledgehammer (Isabelle) (software) https://isabelle.in.tum.de/website-Isabelle2019/dist/Isabelle2019/doc/sledgehammer.pdf : Isabelle/HOL component that translates a single proof goal to TPTP/SMT first-order form and fires it at many independent external ATPs (E, Vampire, SPASS, Zipperposition, Z3, veriT, ...), then reconstructs any found proof back inside Isabelle's trusted kernel.

### universal interchange format (1)

- [2] OMDoc/MMT and proof-library exports (software) https://link.springer.com/article/10.1007/s10817-021-09604-0 : Foundation-independent representation language (OMDoc/MMT) into which major proof-assistant libraries (Coq, HOL Light, IMPS, Isabelle, Mizar, PVS) have been exported, aimed at cross-system interoperability of formal libraries.

### single-kernel autoformalization benchmark (1)

- [1] VeriBench (Stanford) (benchmark) https://cs.stanford.edu/people/brando9/professional_documents/papers/NeurIPS_2026_VeriBench.pdf : 884-task benchmark for agentic Python-to-Lean-4 autoformalization, scored by a conjunctive metric (compilation, proof closure, theorem-gold equivalence) -- single target kernel (Lean 4) only.

### polyglot verification (1)

- [2] PolyVer (paper) https://arxiv.org/abs/2503.03207 : Compositional approach for modeling and verifying polyglot systems (components written in different programming languages) by giving each component's contract to the verifier appropriate for its source language and composing the results.

### differential fuzzing across independent provers (1)

- [2] zkvmBlast (software) https://blog.zksecurity.xyz/posts/zkvmblast/ : Differential-fuzzing harness that runs one RISC-V program across several zkVM provers (SP1, Pico, OpenVM, RISC0) plus a reference simulator and reports every disagreement, catching soundness/completeness/executor-correctness bugs.

### spark (1)

- [4] AdaCore - SPARK and Formal Verification Toolchain (project) https://www.adacore.com/ : AdaCore provides SPARK language and toolchain for formally verified Ada/SPARK code with GNATprove and Why3 integration.

### lean (1)

- [5] Lean Prover Community - Code Verification & Synthesis (project) https://lean-lang.org/ : Lean is a proof assistant used in tup's seven-kernel strategy, with active community work on code verification and synthesis.

### coq (1)

- [5] Rocq/Coq Formal Proof Assistant - Industrial Applications (project) https://coq.inria.fr/ : Coq is a proof assistant and formal methods foundation used in tup's seven-kernel strategy, with industrial verification applications.

### f* (1)

- [5] F* Formal Language - Verified Program Synthesis (project) https://www.fstar-lang.org/ : F* is a dependently-typed language for program verification developed jointly by Microsoft Research and Inria, used in tup's kernel set.

### verus (1)

- [5] Verus - Formal Verification for Rust (project) https://verus.dev/ : Verus is a formal verification system for Rust code, used in tup's seven-kernel strategy for verifying systems code.

### dafny (1)

- [5] Dafny Formal Verification Language (project) https://dafny.org/ : Dafny is a language and verifier for formally verified code, core to tup's DafnyBench lifter and a primary verification kernel.

### bit-for-bit-verification (1)

- [5] Reproducible Builds (project) https://reproducible-builds.org/ : Set of software development practices creating independently-verifiable path from source to binary through deterministic builds and documented build environments.

### source-based-building (1)

- [5] Linux From Scratch (LFS) (project) https://www.linuxfromscratch.org/ : Project providing step-by-step instructions to build a complete Linux system from source code, giving users full understanding and control of their system.

### in-toto-attestation (1)

- [4] Witness (software) https://witness.dev/ : Tool for creating in-toto attestations that document who did what and what tools were used in software supply chain activities.

### reproducible-identifiers (1)

- [4] OmniBOR (software) https://omnibor.io/ : System providing reproducible artifact identifiers and fine-grained build dependency tracking across software artifacts.

### reproducible-packages (1)

- [4] Debian's Reproducible Builds Implementation (project) https://wiki.debian.org/ReproducibleBuilds : Debian's approach to ensuring byte-for-byte reproducibility of package builds through fixed environments and .buildinfo control files documenting build conditions.

### update-integrity (1)

- [3] The Update Framework (TUF) (project) https://theupdateframework.io/ : Framework for securing software update systems by maintaining integrity even when repositories or signing keys are compromised.

### sbom-standard (1)

- [3] SPDX (System Package Data Exchange) (standard) https://spdx.dev/ : International open standard (ISO/IEC 5962:2021) for representing systems with software components as Software Bills of Materials and security references.

### bom-standard (1)

- [3] CycloneDX (standard) https://cyclonedx.org/ : Full-stack Bill of Materials standard (ECMA-424) providing advanced supply-chain capabilities including SBOM, CBOM, VEX, and HBOM for cyber risk reduction.

### embedded-linux-building (1)

- [3] Yocto Project (project) https://www.yoctoproject.org/ : Open-source platform for constructing custom Linux-based operating systems for any hardware architecture with reproducible builds and SBOM generation.

### ci-cd-automation (1)

- [2] Tekton (software) https://tekton.dev/ : Open-source CI/CD framework for creating cloud-native build, test, and deployment systems across vendors and on-premise infrastructure.

### deployment-verification (1)

- [2] Binary Authorization (software) https://docs.cloud.google.com/binary-authorization/docs : Google Cloud service enforcing policy-based deployment controls requiring container image attestations before they can run on GKE, Cloud Run, and Distributed Cloud.

### container-standards (1)

- [2] Open Container Initiative (OCI) (standard) https://opencontainers.org/ : Open governance organization defining industry standards for container formats (image-spec, runtime-spec, distribution-spec) enabling interoperability across the container ecosystem.

### application-bundling (1)

- [2] CNAB (Cloud Native Application Bundles) (standard) https://cnab.io/ : Specification for bundling, installing, and managing container-native applications with cryptographic signing, attestation, and verification capabilities.

### multi-prover trust (1)

- [5] QED Manifesto (standard) https://en.wikipedia.org/wiki/QED_manifesto : 1994 foundational proposal for a machine-verified database of mathematics with all proofs automatically checked.

### proof interchange format (1)

- [5] TPTP (Thousands of Problems for Theorem Provers) and TSTP (Solutions) (standard) https://www.tptp.org : Infrastructure and standardized format for automated theorem provers to exchange problems, solutions, and cross-validate results.

### formal proof repository (1)

- [4] Mizar (Mathematical Vernacular) (software) https://www.mizar.org : Proof assistant and formalized mathematics library using natural-language-like syntax, with automated proof checking.

### proof verification (1)

- [4] Metamath (software) https://en.wikipedia.org/wiki/Metamath : Formal language and proof assistant for archiving and verifying mathematical proofs via substitution-based verification.

### solver interoperability (1)

- [4] SMT-LIB and SMT-COMP (Satisfiability Modulo Theories) (standard) https://smt-lib.org : Standardized input format and annual competition enabling different SMT solvers to be cross-validated on common benchmarks.

### multi-solver evaluation (1)

- [3] SAT Competition (International SAT Solver Competition) (standard) https://satcompetition.github.io : Annual competitive evaluation of SAT solvers against standardized benchmarks to identify best solutions and new challenges.

### multi-backend verification (1)

- [4] Frama-C (Framework for Modular Analysis of C) (software) https://www.frama-c.com : Modular verification platform that combines multiple analysis techniques (Eva, WP, E-ACSL) through a plug-in architecture.

### multi-variant family (1)

- [4] HOL Family (HOL4, HOL Light, ProofPower, HOL Zero, Candle) (software) https://en.wikipedia.org/wiki/HOL_(proof_assistant) : Family of interactive theorem provers sharing higher-order logic and LCF approach, with inter-family proof portability via OpenTheory.

### program verification (1)

- [2] KeY System (Java Program Verifier) (software) https://www.key-project.org : Interactive verifier for Java programs using JML specifications and theorem provers to prove correctness for all inputs.

### proof development (1)

- [3] Nuprl (Proof Development System) (software) https://en.wikipedia.org/wiki/Nuprl : Proof development system based on Martin-Löf intuitionistic type theory, with distributed architecture for computer-mediated formal analysis.
