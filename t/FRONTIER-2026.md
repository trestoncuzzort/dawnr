# Where the field stands in 2026, and where t stands in it

2026-09-09. Compiled from three lenses (the frontier map, t's own position against
it, and a ranked list of moves), a critic pass over lens A, and a fourth round of
independent reads that verified, corrected or refuted nearly every numeric claim
those lenses carried.

Five sentences first. The field's best 2026 systems now clear single-kernel Dafny
proof rates in the 80-96% range and put agentic repair loops (compiler error text
fed back for several rounds) at the center of nearly every large gain measured this
year, while spec-fidelity work shows the opposite: even the best autoformalizers
solve full spec-equivalence proving under 2% of the time, and the newest calibrated
fidelity probe still misses roughly a tenth of drifted specs it is asked to catch.
t has one number nobody else in this search reports at all, 60 of 277 DafnyBench-lifted
tasks (t/COVERAGE-lifted-785.md) verified with a certified refutation of a mutant twin simultaneously in all
seven independent proof kernels, which is a structurally stronger anti-vacuity test
than any softer signal (LLM judge, test-suite completeness score, semantic filter)
the frontier uses in its place. t is two to five orders of magnitude behind the
frontier on raw corpus scale and has no agentic repair loop at all, which by the
field's own measurements this year is the single lever that moves numbers the most
for the least new engineering. The moves below are ordered by that logic: build the
repair loop first, because everything else compounds on top of it.

## What front tier means in 2026

Seven axes, each with the headline numbers a 2026 reader would be shown, corrected
where the critic pass or the fourth read found the correction actually held.

### 1. Spec fidelity and autoformalization

The best systems still cannot autoformalize faithfully at scale. CLEVER (NeurIPS
2025 Datasets and Benchmarks Track, confirmed venue; arxiv.org/abs/2505.13938)
requires a generated Lean spec to be proven semantically equivalent to a held-out
reference spec before implementation grading starts at all; across GPT-4o,
Claude-3.7, o4-mini, DeepSeek-R1 and a COPRA proof-search agent, spec-equivalence
proving never exceeds 1.863% at a 600-second budget, and only 1 of 161 problems is
solved fully end to end, and only because that one problem's equivalence proof
happens to be dischargeable by `simp`/`ring`. The Vericoding benchmark
(arxiv.org/abs/2509.22908; POPL 2026 acceptance is stated in t/RELATED-WORK.md, not
independently confirmed from the paper itself) translated 6,174 specs across
Dafny/Verus/Lean via an LLM generate-verify-repair loop and still found about 9% of
successful specs "too weak" and about 15% of translations "poor quality" on manual
audit of a small sample. SpecCoder (arxiv.org/abs/2607.04232) trains a completeness
score (fraction of a mutant pool a spec rejects) from 0.1707 to 0.7820 on
Qwen2.5-Coder-7B, but even after training, true-positive real-bug-catching stays
under a third. The most rigorous fidelity metric published this year is BPF+CPG,
bidirectional provability fingerprinting with counterfactual probe generation, from
"The Faithfulness Gap" (arxiv.org/abs/2606.16541): a calibrated equivalence score
detecting NL-to-Lean semantic drift at 89.6% detection at a fixed 3% false-positive
rate (F1=0.91), beating an LLM-judge baseline (63.3%, F1=0.71) by about 26 points,
over 2,132 to 2,183 labeled pairs (the paper's own totals do not reconcile to the
decimal, an inconsistency in the source, not in this reading of it). A second,
separate 2026 paper, "Fidelity Probes for Specification-Code Alignment"
(arxiv.org/abs/2605.17246), runs the same kind of loop on COBOL/EARS specs against
one company's real 77.7kLOC codebase and gets test-vs-spec fidelity from 62.7% to
93.9% over 8 iterations with a Hoeffding-bounded generalization gap; these are two
distinct systems, not one conflated paper, confirmed by independently fetching
both.

### 2. Proof success rates on standard benchmarks

Frontier single-kernel Dafny numbers are now high and climbing. Vericoding's
model-union Dafny success is 82.2% over 3,029 tasks (best single model: Claude
Opus 4.1 at 67.5%), and DafnyBench's own trend, cited across the field, moved from
68% (Claude 3 Opus, June 2024, arxiv.org/abs/2406.08467's own number) to 96%
(model union, 2025, per Vericoding). AlgoVeri (ICML 2026, confirmed venue;
arxiv.org/abs/2602.09464), a harder hand-aligned benchmark of 77 classical
algorithms across Dafny/Verus/Lean, still collapses by kernel: Gemini-3 Flash
reaches 55.84% on Dafny, 25.97% on Verus, only 9.09% on Lean; after an LLM
semantic filter that catches cheating (`assume false`, `sorry`) and algorithmic
degeneracy (solving an easier variant), those drop to 40.26%/24.68%/7.79%, a
roughly 28% relative loss on Dafny's own best case. On Lean specifically,
Goedel-Code-Prover-8B reaches 62.0% across Verina/Clever/AlgoVeri
(arxiv.org/abs/2603.19329), 2.6x the strongest neural baseline it reports
(BFS-Prover-V2-32B at 23.8%), via decompose-then-complete hierarchical search. For
pure math theorem proving, Seed-Prover (arxiv.org/abs/2507.23726) saturates
MiniF2F (99.6% vs. DeepSeek-Prover-V2's 90.6% and Kimina-Prover's 92.2%) and
solves 331/657 PutnamBench statements against DeepSeek-Prover-V2's 47/657 (a 3.8x-
plus improvement over the correction), and AlphaProof (Nature, 2025,
doi.org/10.1038/s41586-025-09833-y) reached IMO 2024 silver (28/42 points) with
formal-imo at 58.3% and PutnamBench-test at 56.1%, both after up to 500 TPU-days
of per-problem test-time RL; the underlying auto-formalizer translated about 1
million natural-language problems into about 80 million formal Lean statements at
60-64% pass@1 fidelity, confirmed directly from the paper rather than inferred.

### 3. Corpus scale and data pipelines

Scale is now measured in millions. VeruSyn (arxiv.org/abs/2602.04910, the system
name confirmed in the paper's own text) synthesizes 6.9 million Rust programs
each with a verified spec and proof from a roughly 10K-program seed corpus via
self-synthesis plus tutorial-expansion plus agent-trajectory mining, and
fine-tunes a 32B model that beats Claude Sonnet 4.5 on VeruSAGE-Bench (49% vs.
46% accuracy at a 5-round debug budget) at 13x lower per-task API cost. Formal
Disco (arxiv.org/abs/2607.04631) generates over 100,000 verified programs, a
combined total across Dafny, Verus and Frama-C (the paper does not give a
per-language breakdown; do not multiply by three), and gets a fine-tuned
Qwen2.5-Coder-32B to match Claude Opus on DafnyBench annotation (40.4% vs.
41.4% Pass@16). ATLAS (arxiv.org/abs/2512.10173) turns 21.5% of 12,800 TACO
problems into 2,751 verified Dafny programs, decomposed into 19,385 training
examples across 6 task types, a roughly 7x data multiplier per verified
artifact, with the fine-tuned model beating GPT-4 by 12.4 points Pass@5 on
DafnySynthesis (65.8% vs. 53.4%).

### 4. Multi-verifier and cross-kernel work

The Vericoding benchmark spans three kernels but grades each independently, with
no requirement that the same task agree across kernels. AlgoVeri hand-aligns
Dafny/Verus/Lean with a mechanized non-contradiction check, but that mechanized
check runs on a representative sample of hard tasks (Maximum Flow, Tarjan's SCC),
not on every one of the 77. The Lean Kernel Arena (arena.lean-lang.org, fetched
directly) runs 19 independently implemented Lean kernel checkers against a shared
mathlib corpus with an accept/reject/decline convention that never penalizes an
honest decline, and it genuinely does catch real regressions: an older official
release, official-v4.28.0, shows 6 soundness failures against the current test
suite when re-checked. This is real, but it is 19 reimplementations of one logic,
not heterogeneous kernels. Federated Formal Verification
(arxiv.org/abs/2606.02019) is the closest thing to genuine heterogeneity, a
16-backend roster composing per-obligation verdicts into cross-axis convergence
gates on two proprietary trading-system subsystems (a Raft consensus module and a
numeric pricing library), but it discharges obligations by citing a theorem proved
in a different kernel under a human-asserted, explicitly unmechanized
"correspondence certificate," not by independently re-verifying the same program
in each backend; the paper names this as its own principal open problem. hax
(eprint.iacr.org/2025/142) routes one Rust source to whichever single backend
(F*, Coq/Rocq, ProVerif) suits the property wanted (functional correctness in F*
for ML-KEM, protocol security in ProVerif for Bertie's TLS handshake), never
running all backends against the same program for the same property.

### 5. Training loops with verifier rewards, and their failure modes

The dominant 2026 finding is that naive RLVR reward-hacks hard, and this is now
measured rather than only suspected. Tan's MIT thesis (EECS, advised by Max
Tegmark; arxiv.org/abs/2605.30914) shows naive single-turn Dafny RLVR moves
verified reward from 2.2% to 58.1% "almost entirely via spec-gaming"; filtering
plus multi-turn repair with verifier feedback brings held-out verified pass rate
from 9.7% to 31.1%. "When the Reward Suite Is Leaky" (arxiv.org/abs/2607.11022)
preregisters a causal contrast on MBPP: a leaky (weak-test) reward arm rewards
genuinely wrong code on 45.9% of its rollouts on leak-prone tasks versus 2.1% on
clean tasks, and a hardened reward arm (MBPP+, about 105 tests/task) shows no
detectable held-out advantage at matched scale (observed gap 0.20 points against
a preregistered 1.5-point margin), a real null result about whether a harder test
suite alone pays for its overhead. Re:Form (TMLR, confirmed venue;
arxiv.org/abs/2507.16331) trains GRPO on Dafny with a verifier-checked
subset-implication reward and reaches 14.0% pass@1 on a compositional
out-of-domain benchmark (DafnyComp) versus 2.7% for zero-shot Claude used as a
spec generator. Propose-Solve-Verify (arxiv.org/abs/2512.18160) runs a
proposer/solver/verifier self-play loop on Verus reaching up to a 9.61x pass@1
gain over an RFT-only baseline on MBPP-Verified, with an ablation showing
removing solution verification costs a 51.5% relative decline (33.8 points,
65.63% to 31.82% on Dafny2Verus). DafnyComp (arxiv.org/abs/2509.23061)
independently demonstrates the composability failure mode directly: chaining 2-5
already-individually-verifiable functions collapses verification success from
about 53% baseline to 3.69% averaged, a stated "92% performance gap," and a 3.2x
increase in chained-function count produces roughly a 14x decrease in success.

### 6. Agentic repair loops and their cost

Compiler-in-the-loop agents are the single biggest measured lever this year.
"Agentic Proving for Program Verification" (arxiv.org/abs/2605.23772) drives
Claude Opus 4.6 through lean-lsp-mcp with a multi-cycle autoprove routine and
lifts CLEVER's one-shot 0.6-8.7% baseline to 87.5-98.8% success purely from
iterative diagnostic feedback and lemma search, on Lean only. AutoVerus (OOPSLA
2025, confirmed venue; arxiv.org/abs/2409.13082) proves 137/150 (91.3%)
Verus-Bench tasks via an 8-agent error-taxonomy repair bank at an average 8.8 LLM
calls per task, costing about $37 total across the whole benchmark (roughly $0.25
per task). KVerus (ASE 2026, confirmed venue; arxiv.org/abs/2605.03822) adds a
typed dependency graph and lemma-retrieval layer, reaching 51.0% on
repository-scale tasks (vs. 4.5% baseline) and landing 23 functions upstream into
the Asterinas general-purpose kernel's CortenMM module, all patches accepted by
its maintainers. WybeCoder (arxiv.org/abs/2603.29088) shows subgoal-decomposition
scaling with no plateau across 2^4-2^11 LLM calls (74.1% Verina, 62.1% Clever at a
32-turn x 16-sample budget), with one full Heapsort verification costing 357
subagent calls in total. Vero (arxiv.org/abs/2608.13522) is the sharpest
cost-versus-completion contrast: an agent run at "GPT-5.5 xhigh" effort solves
27/43 full multi-module repository tasks at $2,865-2,964 aggregate API cost per
full run of the 43-instance benchmark (roughly $67-69 per task), while per-spec
pass rate (87.3%) substantially overstates full-repository completion (62.8%),
because residual failures cluster into shared "walls" rather than scattering.
Lined up, the field's per-task API cost this year spans roughly two orders of
magnitude: about $0.17-0.25 at the cheap end (VeruSyn's fine-tuned 32B, AutoVerus)
to $67-100+ per task at the expensive end (Vero's frontier-agent full-repository
runs), with no single paper normalizing the two into one $/verified-task curve.

### 7. Deployment

Real deployment evidence splits into a pre-LLM tier and an AI-era tier, and the
pre-LLM tier is much older and larger than the AI-era one. SPARK (a formally
defined Ada subset with GNATprove automation since the 1980s;
en.wikipedia.org/wiki/SPARK_(programming_language)) has decades of certified
deployment: NATS's iFACTS air-traffic tool, Lockheed's C-130J, the Eurofighter
Typhoon, the Tokeneer demonstrator, Rockwell Collins cross-domain solutions, all
certified to DO-178B Level A, DEFSTAN 00-55 or ITSEC E6, with a Praxis engineer's
own quoted defect-rate claim of "10 to 100 times lower" than comparable
non-formal code. Against that pre-LLM baseline, 2026's AI-era wins are narrower:
hax/libcrux's ML-KEM implementation, verified via the F* backend for
panic-freedom and functional correctness, adopted by OpenSSH and by Mozilla for
NSS; Verus (SOSP 2024, doi.org/10.1145/3694715.3695952) integrated a crash-safe
persistent log into a production cloud-storage codebase with throughput matching
libpmemlog on real Optane hardware, and its largest project, a verified
mimalloc port at 17.2K lines, completes 8 of 19 mimalloc-bench benchmarks without
yet reaching performance parity; KVerus's 23-function upstream merge into
Asterinas is the clearest "accepted by real maintainers" AI-era data point;
Anthropic's Fermat's Last Theorem formalization (13 million lines of Lean, 30,300
theorems, 11 days, about 6 billion output tokens, cross-checked by the Lean
kernel itself, a second independent kernel implementation nanoda, and a
comparator tool confirming statement-identity against an external reference) is
the largest-scale demonstration to date of a single, triple-checked AI-agent
artifact, though it is a research showcase, not a deployed system. On raw
maturity, the two tiers are not comparable: SPARK's numbers come from decades of
fielded, human-engineered, certifier-audited systems; the AI-era numbers come
from months-old research artifacts, several still unmerged or still short of
performance parity.

## Where t stands

Axis by axis, t's own numbers beside the frontier's, from ROADMAP.md,
LOOP-CURVE.md, COVERAGE-lifted-785.md, COVERAGE-nl.md, AGREEMENT.md,
SPEC-EXPERIMENT-mbpp.md and RELATED-WORK.md, checked 2026-09-09.

**1. Spec fidelity.** t has one measured number: on the 7B spec-writing
experiment (SPEC-EXPERIMENT-mbpp.md), 64 of 368 MBPP pool problems produced a
well-formed t task, and of those, 35 restate the function body rather than
stating an independent property (RELATED-WORK.md: 8 of the 10 verified-but-wrong
tasks are that shape). That is a real finding, but it is a manual read of a
table, not a calibrated score. The frontier already has continuous metrics for
exactly this: VERINA defines soundness and completeness against a held-out
reference spec, falling back to property-based testing when proof is
inconclusive; SpecCoder scores Correctness/Completeness/Validity against
thresholds and trains on the accepted trace; The Faithfulness Gap has a
calibrated equivalence score with accept/review/reject bands and a proven
generalization bound. t has no reference-spec oracle, no continuous score, and
no training signal built from one. Where t is ahead here is structural, not
metric: its abstain-or-refute-with-certificate discipline catches the same
failure class (a vacuous or restated spec cannot refute its twin) without a
second hand-written ground-truth spec per task, which VERINA and CLEVER both
require and t's own corpus mostly lacks.

**2. Proof success.** Frontier single-kernel Dafny numbers are high (82.2%
model-union, Vericoding; 96% model-union on DafnyBench). t's comparable number
is much smaller and much harder to compare directly: on the spec experiment's
64 well-formed tasks, dafny gets 43/64 (67%), spark 43/64, verus 40/64, lean
40/64, rocq 38/64, framac 37/64, fstar 11/64 (SPEC-EXPERIMENT-mbpp.md), but
every one of those counts requires the twin to also be refuted with a
kernel-accepted certificate, not verify alone, and the denominator is
single-shot generation with no repair loop, from a raw pool of 368 (so the true
yield against the pool is 43/368, about 12%; 4 of 368 verify with a refuted
twin in all seven columns and pass their own tests). t is behind in raw scale
and behind in having no repair loop to lift that number, but its "verified"
already means something stricter than most of the frontier's "verified."

**3. Corpus scale.** This is where t is furthest behind, by two to five
orders of magnitude on every comparable published corpus. t's lifter has run
277 DafnyBench methods (of a 785-program census, COVERAGE-lifted-785.md),
with 60 verified-with-refuted-twin in all seven kernels and 72 in six. Its
nl/ census covers 24,748 problems but only 599 of 4,239 function-shaped ones
are in t's fragment today (14.1%, COVERAGE-nl.md), and only 1,022 of 20,509
stdin-shaped problems would enter once a signature is extracted. Against
that: VeruSyn's Rust corpus is 6.9M verified programs; Vericoding is 12,504
fidelity-checked tasks across three kernels; Formal Disco reports over 100,000
complete verified programs; ATLAS turned 12,800 attempts into 2,751 verified
Dafny programs and a 19,385-example training set. None of those corpora is
checked for the thing t checks (seven-kernel joint agreement plus certified
refutation), so the comparison is not fully like for like, but the raw scale
gap is real and large, and t names it as its own next hurdle (12.7's construct
waves, the nl/ census's function-shaped tier) rather than disputing it.

**4. Multi-verifier.** This is t's clearest lead, and the number nobody else
reports: 60 of 277 lifted tasks verified with a refuted twin
simultaneously in all seven independent kernels (Dafny, Verus, SPARK, Frama-C
WP, Lean 4, Rocq, F*), with a full per-kernel breakdown of every non-agreeing
cell (AGREEMENT.md's 23-task fixture, at 20 of 23 in all seven; COVERAGE-lifted-785.md's
larger sweep). The frontier's widest comparable efforts are narrower:
Vericoding spans three kernels with no requirement that the same task pass
all three; VerifyThisBench targets seven backends (Dafny, Why3, VeriFast,
VerCors, Frama-C, Verus, CBMC) but grades each task against whichever one
target it was written for, not seven columns of the same task jointly, and
every one of its nine evaluated models scores under 4% zero-shot pass on the
full task; AlgoVeri hand-aligns three kernels with only a sampled mechanized
non-contradiction check. Nobody else requires a single task's spec to be
independently lowered into seven backends and have every one of them both
verify the real program and produce a kernel-accepted refutation certificate
for the mutant twin. RELATED-WORK.md's own gap analysis (section 2) confirms
this after its own search: Arena and Comparator check one kernel with multiple
checkers, SV-COMP checks one program in one language, nothing checks seven
independent lowerings of the same task with a joint pass bar.

**5. Training loops.** Behind, sharply, though the second round is the first
sign of a real training effect rather than only a path effect. t has one
measured QLoRA DPO round at 1.5B (72 steps, 15 minutes, 59 positives and 189
preference pairs, LOOP-CURVE.md) and now a second, expert-iteration round
measured (8 samples/problem, tests folded into the reward, per ROADMAP
WS-18). Round 1's held-out lift was modest and mostly attributable to the
inference path, not the DPO round itself: on the original 322-problem
held-out set, well-formed count went 25 (ollama baseline) to 41 (same-path
control) to 45 (round 1), with the control column existing precisely because
the path change moved the number more than training did. Round 2, graded on
the curve's own fixed 161-problem eval split (recomputed for all rounds on
that split, so the numbers differ from the 322-problem ones above), shows a
different shape: well-formed stays flat across rounds (14/24/24/23) and tests
passing actually drops (3/5/5/3), but verified-with-a-refuted-twin-in-some-
column nearly doubles from round 1 to round 2 (9 to 15) and verified in all
seven kernels triples (1 to 3), the first case in the curve where a training
round, not the inference path, moved the strictest number. Whether that holds
up under a preregistered ablation against a matched control (move 14 below)
is still open. Compare AlphaProof's roughly 180,000 TPU-days across
auto-formalization, main RL and Mathlib fine-tuning; Seed-Prover's
expert-iteration SFT plus RL on a frontier-scale model with a distributed
search cluster and a persistent lemma pool; Re:Form's GRPO ladder across five
model sizes with a verifier-checked reward; VeruSyn's SFT on a 6.9M-program
corpus. t's loop is real and end to end, but it is a first curve, not yet a
scaled ladder, and it has no RL (GRPO/PPO-style) component at all yet.

**6. Agentic repair.** This is t's largest single gap, and arguably the
cheapest move available given the frontier evidence. t's generation is
single-shot: one reply per problem, temperature 0, no retry against a
kernel's own error message. The frontier's biggest jumps this year come
almost entirely from adding exactly that: CLEVER's Lean LSP autoprove loop
took a 0.6-8.7% one-shot baseline to 87.5-98.8%; AutoVerus's three-phase
repair took a bare-LLM baseline of 44.7% to 91.3%; AlgoVeri's 8-15-round
verifier-feedback repair nearly triples Gemini-3's raw Dafny pass rate; Tan's
multi-turn RLVR moved Dafny/APPS held-out pass rate from 9.7% to 31.1%. t has
no per-kernel error-to-prompt adapter for any of its seven backends, so this
lever, unlike most of the others, is not scaling work, it is unbuilt
infrastructure work, and RELATED-WORK.md's own gap list does not yet name it
as a planned move.

**7. Deployment.** Behind, and not yet attempted, with a caveat the frontier
map itself needs: the honest deployment comparison is not t versus 2026's
AI-era wins, it is t versus SPARK's own decades of certified, fielded,
non-AI-assisted deployment (iFACTS, the C-130J, the Eurofighter, Tokeneer), a
maturity tier no 2026 AI-verification system, this survey included, has
reached either. Within the AI-era tier: KVerus's 23 functions merged
upstream into Asterinas's CortenMM module; libcrux's ML-KEM adopted by
OpenSSH and Mozilla NSS; Anthropic's Fermat's Last Theorem formalization,
cross-checked by an independent second kernel implementation and a
comparator tool. t has no IDE integration, no external deployment, and
ROADMAP.md names IDE/editor support as a stated 1.0-bar goal, not yet built
(surface syntax landed 2026-09-04 but is "wired into nothing on purpose").

**Summary.** t leads on one axis nobody else has measured at all (seven-way
joint kernel agreement with certified refutation, 60/277), and its twin
mechanism is a structurally stronger anti-vacuity check than most of the
frontier's LLM-judge or test-suite alternatives. It is behind on corpus
scale, training-loop sophistication, and especially agentic repair, where
the field's single most reliable lever this year is entirely unbuilt in t.
Raw proof-success percentages between t and the frontier are not directly
comparable, because t's "verified" bar is strictly harder (joint seven-kernel
verify-plus-certified-refutation) while its generation is strictly easier to
fail (single-shot, no repair, from a much smaller and less curated pool).

## The moves

Ranked by expected effect per unit of work. t numbers are from ROADMAP.md
12.7/12.8/WS-18, LOOP-CURVE.md, COVERAGE-lifted-785.md, COVERAGE-nl.md and
RELATED-WORK.md as of 2026-09-09.

**1. Kernel-error repair loop in the spec-writer, one bounded retry per
kernel.** Build: today's spec experiment and round-2 sampler are one-shot
per sample; add a loop that feeds each kernel's own failure text back for up
to 3-5 retries before scoring. Evidence: Tan (arxiv.org/abs/2605.30914) took
Dafny/APPS held-out pass rate from 9.7% to 31.1% by adding exactly this turn;
AutoVerus's error-driven repair phase alone solved 37 of 150 tasks on top of
its preliminary-generation stage. Effect on t: directly attacks the
35-of-64 restate-the-body finding and the round-1 curve's flat DPO effect
(well-formed 25/41/45 on the held-out 322, most of the gain already came
from the inference path, not training) by giving the model the failing
kernel's actual counterexample instead of a blind resample. First hurdle:
only Dafny's error format is exercised at any scale; a per-kernel
error-to-prompt adapter has to exist for at least Verus and Lean before a
uniform retry loop can be measured.
Verification: corrected: Tan's 9.7%-to-31.1% figure is real but the paper's
own limitations section calls it confounded across several simultaneous
changes, not the isolated effect of a bounded repair turn, and the AutoVerus
37-of-150 claim does not appear in the cited source at all; the first hurdle
should read that no kernel yet has a working error-to-prompt adapter, not
that Verus and Lean merely need to catch up to Dafny, and the effect should
not claim credit for the restate-the-body finding, which move 2 targets.

**2. Turn the twin ladder into a completeness score, not a single pass/fail
twin.** Build: t already has seven mutation operators (off-by-one, wrong-var,
collapse-if, negate-cond, compare-flip, boundary-swap, invariant-drop,
LOOP-CURVE.md's preference-pair breakdown). Score a candidate spec by what
fraction of that pool it refutes, not by one primary twin, using a cheap
single-kernel (Dafny) pre-filter before the full seven-kernel refutation
pass. Evidence: SpecCoder's completeness metric moved 0.1707 to 0.7820
(+358%) on the same lever (arxiv.org/abs/2607.04232); MutDafny measured a
real weak-spec rate (about 1 per 241 lines) this way on 118,458 mutants over
794 programs (arxiv.org/abs/2511.15403). Effect on t: gives the "restates the
body" finding a number, and should raise the fraction of specs that are
non-vacuous before they ever reach seven-kernel grading. First hurdle: full
seven-kernel refutation of many mutants per candidate is too expensive
inside a training loop without the Dafny-only pre-filter built first.
Verification: corrected: the SpecCoder and MutDafny numbers check out
exactly, but SPEC-EXPERIMENT-mbpp.md's own reading shows 34 of the 35
restate-the-body tasks already get refuted under today's single-twin rule,
so a completeness score over the mutation pool will not separate vacuous
specs from genuine ones and does not give that finding a number; the free
interpreter-level completeness measurement over the existing 64-task pool
should run before any Dafny pre-filter is built.

**3. Scale round-2 expert iteration and add verifier-guided branching
instead of flat sampling.** Build: round 2 already samples 8 answers per
problem from the round-1 adapter over a 207-train/161-eval split
(ROADMAP.md WS-18). Replace flat resampling with branching on partial
diagnostics (which invariant clause the kernel accepted vs. rejected).
Evidence: AlphaVerus's Treefinement took exploration-only 27.1% to 32.9% on
HumanEval-Verus purely from branch-on-error-message search
(arxiv.org/abs/2412.06176); Seed-Prover's tiered search gets a similar jump
from bounded, lemma-pooled repair over flat sampling. Effect on t: should
push the all-seven-verified count past 42/204-209 and move six-of-seven
tasks (61 of 204-209, mostly blocked by lean and framac residuals) toward
seven-of-seven. First hurdle: needs move 1's per-kernel error adapter as a
prerequisite; without it there is no signal to branch on.
Verification: corrected: AlphaVerus's Treefinement number is confirmed but
is a Llama-3.1-70B result using REBASE tree search over verifier scores and
error messages together, not GPT-4o or error-message branching alone, and
the uncited Seed-Prover claim should be dropped or sourced separately; the
expected effect cites the wrong instrument, since 42/61-of-209 comes from
the lifted-DafnyBench sweep, not the loop's own 161-task held-out eval,
where round 2 actually measures all-seven at 3/161 and some-column at
15/161.

**4. Finish the strings-and-sequences wave already landed, then land string
library operations.** Build: per ROADMAP 12.7, sequence literals,
concatenation and slices, and strings as sequences of code points, both
landed as notation and semantics on 2026-09-10 (ahead of this survey's
2026-09-09 census snapshot, so this move is already partly done, not
open-ended). What remains open: LIFTER-DECISIONS.md row 28 (mapping Dafny's
`string`/`char` to seq/int), the spec experiment's prompt and pool version 2
carrying the new forms, and the nl/ census's next-largest gap after
string-as-seq, `string-lib` (the Python string library itself: split, join,
count, strip, format), which blocks 13,266 nl/ problems and is the sole
blocker for 298 function-shaped ones (COVERAGE-nl.md). Evidence: t's own two
censuses (DafnyBench and nl/) both ranked the string construct top before it
landed; DafnyComp and AlgoVeri both show construct gaps compound
superlinearly once composition is at stake, so closing this wave's loose
ends before opening a new one is worth more than starting the next
construct early. Effect on t: unblocks the string-library tier of nl/
without a new semantics decision. First hurdle: `string-lib` is a Python
library surface, not a value construct like the ones 12.7 has landed so
far, so it needs its own hazard survey (which of split/join/strip/format
have a clean semantics across all seven kernels) before a lifter row can be
written.
Verification: corrected: DafnyComp's superlinear-composition claim is
confirmed, but the DafnyBench census ranked multi-return top across the
full 643-program corpus, not string-char, which led only within the
narrower MBPP-DFY subfamily; and string-lib should be expected to need its
own new SPEC.md semantics decision under 12.7's own discipline, not a
bypass of one, making this a candidate next wave rather than the roadmap's
stated next step.

**5. Extract a signature from stdin-shaped nl/ problems as a construct.**
Build: 20,509 of 24,748 nl/ problems are stdin-shaped; 1,022 would enter
fragment today once a signature can be mechanically extracted from the
input format (COVERAGE-nl.md), up from 361 before the sequence and string
waves landed. This roughly doubles the addressable APPS/CodeContests slice
at almost no new proof-kernel cost, since the body construct needs are
mostly unchanged once a signature exists. Evidence: FVAPPS
(arxiv.org/abs/2502.05714) and SpecCoder both show real gains come from
mining existing test/IO structure into formal shape, not from hand-authoring;
Vericoding's scale (12,504 tasks) came from exactly this kind of mechanical
repurposing of existing corpora. Effect on t: nl/ fragment potentially grows
past its current 599 function-shaped count without a single new value
construct. First hurdle: "signature from stdin" has to be defined as its
own construct with a semantics and a census gate, per 12.7's discipline;
today it is explicitly named as unmeasured.
Verification: corrected: the SpecCoder/Vericoding/12,504-task claim does not
appear anywhere in the cited FVAPPS paper and looks misattributed; the 698
figure is also an unvalidated lexical proxy by COVERAGE-nl.md's own
admission, and the repo's own COVERAGE-nl-stdin.md already measured the
real, validated number at 203 of 20,509, so the effect should read roughly
+40% over 511 (to about 714), not a doubling, and the extraction instrument
already exists; what remains is a per-kernel SPEC.md semantics decision.

**6. Publish a per-kernel, per-construct bottleneck matrix like Lean Kernel
Arena's.** Build: for every task in the 204-209 sweep, record which of the
seven kernels is the reason it is six-of-seven and not seven-of-seven, the
way Arena's table isolates individual checkers by name. Evidence: Lean
Kernel Arena (arena.lean-lang.org, confirmed by direct fetch) makes exactly
this kind of per-checker gap legible and versioned, including catching a
real regression (official-v4.28.0's 6 soundness failures against the
current suite); RELATED-WORK.md already names Arena's decline/reject/crash
split as something t's abstain discipline should adopt explicitly in the
table legend. Effect on t: turns "61 in six kernels" into an actionable
list; current residuals already visible from COVERAGE-lifted-785.md's own
prose are lean's remaining seq-loop tasks (rotate, swapFirstAndLast,
linearSearch, pancakesort, getEven) and framac's loop-twin timeouts and its
fresh-concatenation refusal. First hurdle: no such matrix exists yet; it is
a reporting change on top of the existing sweep, not new proof work, so it
should ship before move 7.
Verification: corrected: Lean Kernel Arena's regression claim and checker
count are confirmed exactly, and the matrix itself computes cleanly today
(lean sole-blocks 21 of the 61 six-of-seven tasks, fstar 19, framac 9, rocq
7, verus 5, spark 0), but the named residual list is wrong for four of the
five tasks (rotate and pancakesort are not six-of-seven tasks at all, and
getEven/swapFirstAndLast are jointly blocked by framac as well as lean) and
fstar, not just lean and framac, is a bottleneck at least as prominent.

**7. Close spark's seq-equality gap and the verus/framac div-in-loop-guard
abstentions.** Build: spark currently abstains on whole-sequence `==`
(unlowered, a task stating it reads MALFORMED) and both verus and framac
abstain on div inside a loop guard on the two MBPP-DFY IsPrime shapes
(ROADMAP 12.7's own landing notes name both as concrete, closed
residuals, not open-ended ones). Evidence: KVerus (arxiv.org/abs/2605.03822)
shows a retrieval/lemma-bank approach specifically helps a verifier's
weakest constructs; rocq's own `t_upd`/`t_fill` opaque-lemma pattern is
already t's working template for exactly this kind of gap. Effect on t:
spark is currently at 172 of 277 in the latest sweep (COVERAGE-lifted-785.md),
behind dafny's 231; closing seq-equality alone should move a meaningful
share of the 72 six-of-seven tasks that spark blocks into seven-of-seven.
First hurdle: spark's generic sequence type has no visible `=` without a
`use` clause that changes every seq-parameter task's signature, a real
language-design tradeoff that needs a decision recorded in SPEC.md before
landing.
Verification: corrected: KVerus is real but covers only Verus/Rust, not
spark or Frama-C, and the rocq t_upd/t_fill claim is t's own reasoning, not
sourced from KVerus; more substantively, the div-in-loop-guard abstentions
are stale (already largely closed by the guard-obligation work per
ROADMAP's own latest note), and per-task analysis shows spark is the sole
blocker on none of the 61 six-of-seven tasks, so closing its seq-equality
gap is a design-cleanliness move with no measured effect on that count.

**8. Publish the cross-kernel twin/certificate discipline itself as t's
field-facing artifact.** Build: no other system requires both VERIFY on the
real program and REFUTE-with-a-kernel-accepted-certificate on a
witness-bearing twin across seven independently implemented kernels
simultaneously. Package AGREEMENT.md's format, with Arena's abstain/decline
distinction folded in explicitly, as a standalone comparable artifact.
Evidence: every read in this survey with a twin/mutant mechanism at all
(MutDafny, SpecCoder, AlgoVeri's semantic filter, Vero's axiom allowlist)
uses a single kernel and a softer signal (still-verifies, LLM judge,
syntactic denylist); none requires an independently checkable falsification
certificate across seven backends. Vero's axiom-allowlist and
declaration-screening layers (catching 368 native_decide escapes and one
decidability-laundering case across 20,440 differential tests,
arxiv.org/abs/2608.13522) and SV-COMP's asymmetric scoring (a wrong proof
costs 16x a false alarm) are the two nearest analogues, both single-kernel
or single-property, not per-task dual-grading across seven backends. Effect:
this is t's actual novelty claim for the paper, not a training-loop lever;
it needs no new proof work, only a clean write-up. First hurdle: nothing
technical, but ROADMAP 13.3 (what a verified twin means) is still open, so
this move's headline numbers should be re-pulled once 13.3 is resolved; a
proposed escape-hatch audit was checked separately and dropped, since the
per-kernel allowlists it called for already exist (see "Dropped after
verification" below).
Verification: corrected: the core novelty claim is sound and already
measured at 209-task sweep scale, but the Vero citation is misstated (368
is total axiom-allowlist rejections with native_decide only the dominant
pattern, not all 368; the decidability-laundering case is described by Vero
as an evasion that is not caught; and the 20,440 figure comes from an
unrelated implemented_by exploit); also this move's headline numbers should
be re-pulled once ROADMAP 13.3 is resolved.

**10. Run t's harness against AlgoVeri as an external, cited comparison.**
Build: AlgoVeri's 77 classical-algorithm tasks are already hand-aligned
across Dafny, Verus and Lean, three of t's seven kernels. Translate the
in-fragment subset into t source and report per-kernel verify-plus-refute
rates directly next to AlgoVeri's own table (Gemini-3 Flash: Dafny
55.84/40.26, Verus 25.97/24.68, Lean 9.09/7.79). Evidence: AlgoVeri (ICML
2026) is a confirmed-venue, recent benchmark with a semantic-filter gap
t's twin discipline structurally avoids; this move produces the first
apples-to-apples number against a named, recent paper instead of only t's
internal sweep count. Effect: converts "42 of 204-209 in all seven" into a
citable comparison a reader outside the project can check. First hurdle:
AlgoVeri leans on graphs and trees, outside t's current seq/array construct
range; a construct-coverage census of the 77 tasks against t's construct
list has to run first.
Verification: keep: AlgoVeri's venue and Gemini-3 Flash figures (Dafny
55.84/40.26, Verus 25.97/24.68, Lean 9.09/7.79) are confirmed exactly
against the paper, the effect is consistent with t's measured 42/209
all-seven count, and the first hurdle is accurate and unresolved.

**11. Finish MBPP-DFY to half (ROADMAP 16.2), t's own nearest-term benchmark
hurdle.** Build: currently 59 of 164 lifted, 9 in all seven kernels (per the
latest sweep, up from 26 lifted/5 in all seven measured 2026-09-06); the
DONE WHEN bar is 82 of 164 lifted and verified with a refuted twin in all
seven. Evidence: Misu et al. (arxiv.org/abs/2402.00247), the paper this
corpus comes from, is a well-cited small Dafny-synthesis benchmark (their
own Dynamic Few-Shot GPT-4 result reaches 64.04% raw verify@5, with a
human-graded "Strong postcondition" rate of about 58%); hitting the coverage
bar gives t a number directly comparable to that lineage. Effect: this is
already a named roadmap hurdle with a DONE WHEN; treat it as the fastest
concrete win since the lifter and gate order already exist, it just needs
more construct coverage run through it. First hurdle: exactly the ones
already logged in 12.7's lifter residuals (the two-binder quantifier chains,
the `L_inv_0`/`L_ens` checker lemma gaps on for-loop invariants and array
quantifiers, string/cast/slice gaps).
Verification: corrected: Misu et al.'s verify@5 64.04% and about-58%
strong-postcondition figures are confirmed exactly, but the lifted count is
stale (59 of 164, not 42, after the seq-ops wave landed; the all-seven
count is now 9), and "fastest concrete win" overstates it: the all-seven
bar has crawled (5 to 9 across construct waves) against real named
blockers, including an undesigned quantifier semantics and unclosed
per-kernel limits, so expect easy lifted-count progress but a slow grind
toward the all-seven bar.

**12. Apply a task-decomposition data multiplier to t's existing verified
corpus before spending on new formalization.** Build: every one of t's
roughly 42 all-seven and 61 six-of-seven tasks can mechanically emit
NL-to-spec, spec-to-code, spec-repair and proof-infilling variants, the way
ATLAS turned 2,751 verified Dafny programs into 19,385 training examples
(about 7x). Evidence: ATLAS (arxiv.org/abs/2512.10173); SAFE
(arxiv.org/abs/2410.15756) similarly multiplies verified Rust proofs into
repair triplets, and its own debugging-loss ablation lifted DeepSeekCoder
from 43.17% to 49.64% Accuracy@2 on VerusBench purely from the second
objective. Effect: t's current training data (59 positives, 189 preference
pairs for round 1) is two to three orders of magnitude below any
front-tier system's SFT/DPO corpus; this multiplies the existing verified
set to the several-hundred range at zero new proof cost, feeding round 2
and beyond. First hurdle: repair-task examples need a captured (failed
attempt, kernel error, fix) trail per kernel, which the harness does not
retain today; this is a prerequisite shared with move 1.
Verification: corrected: ATLAS's 7x figure and t's own corpus counts (59
positives, 189 pairs) are confirmed exactly, but the SAFE figure is
mislabeled: 43.17% is SAFE's Accuracy@1, not Accuracy@2, and the
matched-budget debugging-objective lift is actually 46.76% to 49.64%
Accuracy@2 (+2.88 points); also, of the four proposed variants, only
spec-repair actually needs the error-capture plumbing named as the hurdle.

**13. Train a self-debugging objective once error triples exist.** Build:
mine (wrong artifact, kernel error text, fixed artifact) triples from the
sweep's own failures and round-2's rejected samples; add a debugging loss
alongside the generation loss, as SAFE does. Evidence: SAFE's debugging
loss lifted DeepSeekCoder from 43.17% to 49.64% Accuracy@2 on VerusBench
purely from this second objective. Effect: should compound with moves 1 and
12 once both exist. First hurdle: strictly downstream of moves 1 and 12; do
not start before the error-capture plumbing exists.
Verification: corrected: the SAFE figure repeats move 12's mislabeling
(43.17% is Accuracy@1, not Accuracy@2; the matched-budget lift is 46.76% to
49.64%, +2.88 points), and this move also sits behind ROADMAP's own
next-named hurdles (the parse wall and scaling positives into the hundreds
per round), not only behind moves 1 and 12.

**14. Run t's own preregistered leaky-vs-hardened reward ablation.** Build:
train round 2 (or a small matched round) under two arms, VERIFY-only-in-one-
kernel versus full seven-kernel VERIFY+REFUTE-twin, matched seeds, and
report the held-out gap against a preregistered margin. Evidence: "When the
Reward Suite Is Leaky" (arxiv.org/abs/2607.11022) found only a 0.20-point
gap against a 1.5-point margin for a hardened test suite over a leaky one
at matched scale, a genuine null result worth knowing before assuming the
twin discipline pays for its training cost. Effect: either confirms the
twin reward is worth its multi-kernel-call overhead per candidate, or
reveals it isn't yet at 1.5B scale, which changes how hard to push moves 2
and 3. First hurdle: multiple seeds times two arms times hundreds of steps
is real GPU budget this box has not yet spent on the training loop, and it
competes with the shared-box yield policy already in force.
Verification: corrected: the source and its 0.20-point-gap-against-1.5-point
-margin figure are confirmed exactly, but the first hurdle undersells the
real prerequisite: no VERIFY-only-in-one-kernel reward or dataset path
exists yet in code and has to be built from scratch, while GPU cost per
round has actually been cheap (tens of minutes), so the binding hurdle is
the missing leaky-arm pipeline, not shared-box scheduling.

### Dropped after verification

**Close the escape-hatch/axiom-allowlist gap before claiming the
certificate discipline is sound** (originally ranked 9). Proposed applying
a per-kernel axiom/escape-hatch allowlist (`#print axioms` for Lean, `Print
Assumptions`/coqchk for Rocq, admit/assume scans for F*, no
`assume`/`external_body` for Verus) as new build work. Dropped: this is
already built and hardened in the repo, not an open gap. Direct inspection
of t/verifiers/*.py shows lean.py, rocq.py, verus.py, fstar.py, dafny.py,
framac.py and spark.py all already scan for and ban axioms, admits, sorries,
native_decide-style escapes and their kernel-specific equivalents. The move
also conflated this closed engineering task with ROADMAP 13.3, which is an
unrelated, still-open policy question (what counts as a verified twin, not
an axiom-soundness check), and its Vero citation was misattributed in the
same way as move 8's (see move 8's verification note).

## What t can offer the field

Three results in this survey that nobody else reports, in order of how
directly they answer a question the frontier itself has raised.

**A joint seven-kernel agreement number.** 42 of 204-209 lifted DafnyBench
tasks verify AND have a mutant twin refuted via a kernel-accepted
certificate, simultaneously, in Dafny, Verus, SPARK, Frama-C WP, Lean 4,
Rocq and F*. Every multi-kernel effort this survey found is narrower:
Vericoding grades three kernels independently with no cross-kernel
requirement; AlgoVeri hand-aligns three kernels with a mechanized
non-contradiction check run only on a sample; Federated Formal
Verification composes 16 backends by citing a theorem across kernels under
an explicitly unmechanized human correspondence certificate, never
independently re-verifying the same program in each one. Nobody in this
search independently re-lowers and re-verifies the same task across seven
kernels and checks that all seven agree.

**A structural anti-vacuity test that needs no reference spec.** The
field's calibrated fidelity metrics (The Faithfulness Gap's BPF+CPG,
89.6% F1=0.91; VERINA's soundness/completeness) all require a second,
independently authored ground-truth spec to compare against. t's
twin-refutation gate catches the same failure class, a spec that would
pass a weaker check by being vacuous or restated, without one: if the twin
cannot be refuted by a kernel-accepted certificate, the column abstains.
This works precisely where the frontier's reference-spec methods cannot,
on raw nl/ problems with no formal ground truth at all, which is most of
t's actual target corpus.

**An honest single-shot, no-repair baseline at scale.** Because t's
generation has no repair loop, its 43/64 (verify) and 4/368 (verify, refute,
and pass tests, in all seven kernels) numbers are a clean floor: what a
7B model does with one shot, temperature zero, against a strictly harder
grading bar than most of the frontier's "verified." Every comparably-scaled
frontier number this survey found already includes several rounds of
repair (AutoVerus's 8.8 calls/task, AlgoVeri's 8-15 rounds, CLEVER's
autoprove loop). A field that wants to isolate how much of its own
reported gain comes from repair versus from the base model's one-shot
capability has, in t's numbers, a data point produced under a harder
grading bar and zero repair, which move 1 above would then let it compare
before-and-after on the same corpus.

## Sources

One line per verified read: title, venue and year, URL, one-line claim, and
the lens that found it. Sorted by the axis it speaks to.

**Axis 1, spec fidelity**

- CLEVER, NeurIPS 2025 Datasets and Benchmarks Track. arxiv.org/abs/2505.13938. Spec-equivalence proving tops out under 2% at a 600s budget; 1/161 solved end to end. Lens A, verified.
- A benchmark for vericoding: formally verified program synthesis, arXiv 2025 (POPL 2026 per t/RELATED-WORK.md, not independently confirmed). arxiv.org/abs/2509.22908. 6,174 translated specs, about 9% too weak / 15% poor quality on manual audit. Lens A, verified.
- Teaching Code LLMs to Reason with Intermediate Formal Specifications (SpecCoder), arXiv 2026. arxiv.org/abs/2607.04232. Completeness score trainable 0.17 to 0.78; true-positive bug catching stays under a third. Lens A, verified.
- The Faithfulness Gap: Certifying Semantic Equivalence Between NL and Formal Statements, arXiv 2026. arxiv.org/abs/2606.16541. BPF+CPG detects NL-to-Lean drift at 89.6% (F1=0.91) at 3% FPR, beating an LLM judge by 26 points. Lens A, verified; not conflated with the next entry.
- Fidelity Probes for Specification-Code Alignment, arXiv 2026. arxiv.org/abs/2605.17246. A distinct system: COBOL/EARS fidelity from 62.7% to 93.9% over 8 iterations with a Hoeffding-bounded generalization gap. Critic gap, extra round.
- VERINA: Benchmarking Verifiable Code Generation, arXiv 2025-2026. arxiv.org/abs/2505.23135. Defines soundness/completeness against a held-out ground-truth spec with a property-based-testing fallback. Lens A, verified.
- Beyond Postconditions: Can LLMs infer Formal Contracts for Automatic Software Verification?, arXiv 2025. arxiv.org/abs/2510.12702. Precondition inference (not just postconditions) collapses unsoundness from about 80% to about 11%. Extra round.

**Axis 2, proof success**

- DafnyBench: A Benchmark for Formal Software Verification, arXiv 2024. arxiv.org/abs/2406.08467. 68% best model (Claude 3 Opus) on 782 programs at launch; the field's own cited floor for the 68%-to-96% trend. Lens A, verified.
- AlgoVeri: An Aligned Benchmark for Verified Code Generation on Classical Algorithms, ICML 2026. arxiv.org/abs/2602.09464. Dafny-Verus-Lean collapse (55.84/25.97/9.09% raw for Gemini-3 Flash); semantic filter costs about 28% relative on Dafny. Lens A and critic, both verified with corrections.
- Goedel-Code-Prover: Hierarchical Proof Search for Open SOTA Code Verification, COLM 2026. arxiv.org/abs/2603.19329. 62.0% across Verina/Clever/AlgoVeri, 2.6x the strongest neural baseline. Lens A, verified.
- Seed-Prover: Deep and Broad Reasoning for Automated Theorem Proving, arXiv 2025, ByteDance Seed. arxiv.org/abs/2507.23726. Saturates MiniF2F at 100.0%/99.6% (valid/test, medium tier); 331/657 PutnamBench vs. the paper's own cited prior SOTA of 86/657 (Goedel-Prover-V2), at medium tier. Lens A, verified with a correction on one geometry comparison.
- Olympiad-level formal mathematical reasoning with reinforcement learning (AlphaProof), Nature 2025. doi.org/10.1038/s41586-025-09833-y. IMO 2024 silver (28/42); auto-formalizer scale and TPU-day figures confirmed directly from the paper. Lens A, verified with two corrections (fine-tuning-set size, unsourced gold-medal count).
- BFS-Prover: Scalable Best-First Tree Search for LLM-based ATP, arXiv 2025. arxiv.org/abs/2502.03438. 72.95% cumulative MiniF2F pass rate; DPO adds 0.4-0.45 points over SFT at matched budget. Extra round.
- Goedel-Prover-V2: Scaling Formal Theorem Proving with Scaffolded Data Synthesis, arXiv 2025. arxiv.org/abs/2508.03613. 8B model matches a 671B prior SOTA on MiniF2F (84.6% pass@32); PutnamBench 86/657 at pass@184 (self-correction) vs. DeepSeek-Prover-V2-671B's 47/657 at pass@1024. Extra round.
- Verus-SpecGym: An Agentic Environment for Evaluating Specification Autoformalization, arXiv 2026. arxiv.org/abs/2605.26457. Best model 77.8% pass@1 on 581 tasks; LLM-judge misses 26% of failures an executable-spec oracle catches. Extra round.
- MINIF2F-DAFNY: LLM-Guided Mathematical Theorem Proving via Auto-Active Verification, arXiv 2025-2026. arxiv.org/abs/2512.10187. Best model (Claude Opus 4.6) 62.7% pass@4 vs. a 38.9% empty-annotation baseline. Extra round.

**Axis 3, corpus scale**

- Reducing the Costs of Proof Synthesis on Rust Systems by Scaling Up a Seed Training Set (VeruSyn), arXiv 2026. arxiv.org/abs/2602.04910. 6.9M verified Rust programs; fine-tuned 32B beats Claude Sonnet 4.5 at 13x lower cost. Lens A and critic, both verified.
- Formal Disco: Scalable Open-Ended Generation of Formally Verified Programs, arXiv 2026. arxiv.org/abs/2607.04631. Over 100,000 verified programs combined across Dafny/Verus/Frama-C (one total, not per-language). Lens A, verified with a correction.
- ATLAS: Automated Toolkit for Large-Scale Verified Code Synthesis, arXiv 2025-2026. arxiv.org/abs/2512.10173. 2,751 verified Dafny programs from 12,800 attempts, decomposed 7x into 19,385 training examples. Lens A, verified with a small arithmetic correction.
- Proving the Coding Interview: A Benchmark for Formally Verified Code Generation (FVAPPS), arXiv 2026. arxiv.org/abs/2502.05714. 4,715 typechecked Lean specs mined automatically from APPS unit tests via property-based testing. Extra round.

**Axis 4, multi-verifier and cross-kernel**

- Federated Formal Verification: Cross-Backend Citation, Cross-Axis Convergence, and AI-Orchestrated Proof Dispatch, arXiv 2026. arxiv.org/abs/2606.02019. 16-backend roster on two production subsystems; discharges obligations by citing across kernels under an unmechanized correspondence certificate. Critic gap, extra round.
- Lean Kernel Arena, arena.lean-lang.org (live benchmark, no paper). 19 independently implemented Lean kernel checkers; catches a real regression in an official past release (6 soundness failures). Critic gap, extra round, fetched directly.
- hax: Verifying Security-Critical Rust Software using Multiple Provers, IACR ePrint 2025/142. eprint.iacr.org/2025/142. Routes one Rust source to whichever single backend (F*, Rocq, ProVerif) suits the property; libcrux's ML-KEM adopted by OpenSSH and Mozilla NSS. Critic gap, extra round.
- VerifyThisBench: Generating Code, Specifications, and Proofs All at Once, arXiv 2025. arxiv.org/abs/2505.19271. Seven backends targeted, one per task; every model under 4% zero-shot pass. Extra round.
- ITPEval: Benchmarking Formal Translation Across Interactive Theorem Provers, arXiv 2026. arxiv.org/abs/2607.19407. Cross-ITP translation (Lean4/Rocq/Isabelle/HOL Light) with a bidirectional-entailment semantic-equivalence check (BEq); type-checking alone overstates true translation quality by about half in the worst case. Critic gap, extra round.

**Axis 5, training loops and reward hacking**

- Automating Formal Verification with Reinforcement Learning and Recursive Inference (Tan's MIT thesis), arXiv 2026, MIT EECS (advisor Max Tegmark). arxiv.org/abs/2605.30914. Naive RLVR reward-hacks to 58.1%; filtered multi-turn repair reaches 31.1% held out. Lens A, verified, MIT affiliation confirmed.
- When the Reward Suite Is Leaky: A Preregistered Causal Contrast, arXiv 2026. arxiv.org/abs/2607.11022. Auditing every rewarded false positive finds genuinely wrong code in 47.57% of them (record-weighted; two replication families at 45.37% and 62.78%, "large" but not one number); hardening the suite shows no detectable held-out gain at matched scale. Critic gap, extra round.
- Re:Form: Reducing Human Annotations in Scalable Formal Software Verification with RL in LLMs, TMLR 2026. arxiv.org/abs/2507.16331. GRPO on Dafny reaches 14.0% pass@1 on a compositional OOD benchmark vs. 2.7% zero-shot. Lens A, verified.
- Propose, Solve, Verify: Self-Play Through Formal Verification, arXiv 2025-2026. arxiv.org/abs/2512.18160. Self-play on Verus, up to 9.6x pass@1 gain; removing verification costs a 51.5% relative decline. Lens A, verified with a correction.
- Local Success Does Not Compose: Benchmarking LLMs for Compositional Formal Verification (DafnyComp), arXiv 2025. arxiv.org/abs/2509.23061. Chaining 2-5 verified functions collapses success from about 53% to 3.69%. Lens A, verified.

**Axis 6, agentic repair and cost**

- Agentic Proving for Program Verification, arXiv 2026. arxiv.org/abs/2605.23772. Compiler-in-the-loop autoprove takes CLEVER's 0.6-8.7% baseline to 87.5-98.8%. Lens A, verified.
- AutoVerus: Automated Proof Generation for Rust Code, OOPSLA 2025. arxiv.org/abs/2409.13082. 137/150 Verus-Bench tasks, 8.8 calls/task, about $37 total. Lens A, verified with a correction on the baseline's example-advantage.
- KVerus: Scalable and Resilient Formal Verification Proof Generation for Rust Code, ASE 2026. arxiv.org/abs/2605.03822. 51.0% on repository-scale tasks vs. 4.5% baseline; 23 functions merged upstream into Asterinas. Lens A, verified.
- WybeCoder: Verified Imperative Code Generation, arXiv 2026, Meta FAIR. arxiv.org/abs/2603.29088. Subgoal decomposition scales with no plateau across 2^4-2^11 calls. Lens A, verified.
- Vero: Can AI Agents Build Formally Verified Software Repositories?, arXiv 2026. arxiv.org/abs/2608.13522. 27/43 full-repository solves at "GPT-5.5 xhigh"; per-spec pass rate overstates full-repo completion by about 25 points. Lens A, verified; the model-effort label is confirmed, not assumed.
- AlphaVerus: Bootstrapping Formally Verified Code Generation through Self-Improving Translation and Treefinement, arXiv 2024-2025. arxiv.org/abs/2412.06176. Treefinement lifts exploration-only 27.1% to 32.9% on HumanEval-Verus. Lens A and lens C, verified.

**Axis 7, deployment**

- SPARK (programming language), Wikipedia (encyclopedic, not peer-reviewed). en.wikipedia.org/wiki/SPARK_(programming_language). Decades of certified pre-LLM deployment (iFACTS, C-130J, Eurofighter, Tokeneer); a Praxis engineer's own quoted 10-100x defect-rate claim. Critic gap, extra round.
- SPARK Architecture, Quality Assurance and Maturity, AdaCore SPARK User's Guide. docs.adacore.com. 3,600-test regression suite, GNAT2Why statement coverage held above 95%. Critic gap, extra round.
- Verus: A Practical Foundation for Systems Verification, SOSP 2024. doi.org/10.1145/3694715.3695952. Verifies 3-61x faster than prior tools; verified mimalloc port completes 8/19 mimalloc-bench without performance parity yet. Extra round.
- Formalizing Fermat's Last Theorem, Anthropic Research, 2026. anthropic.com/research/formalizing-fermats-last-theorem. 30,300 theorems, 13M lines of Lean, cross-checked by a second independent kernel (nanoda) and a comparator tool. Lens A, verified.

**Axis 4/5/6 crossover, SPARK and Frama-C specific automation (critic gap, all extra round)**

- The Prover Is the Judge: Verified Security Software from AI Coding Agents in Ada/SPARK, arXiv 2026. arxiv.org/abs/2607.14340. 49,280 SPARK proof obligations discharged across 77.7kLOC; two documented cases where full proof discharge survived a real defect.
- Verifying LLM-Generated Code in the Context of Software Verification with Ada/SPARK (Marmaragan), arXiv 2025. arxiv.org/abs/2502.07728. 36/71 (50.7%) SPARK annotation-restoration cases solved by GPT-4o; the only dedicated SPARK LLM-automation number this search found.
- AutoACSL: Synthesizing ACSL Specifications by Integrating LLMs with CPG-Based Static Analysis, arXiv 2026. arxiv.org/abs/2606.20969. CPG-guided prompting lifts Frama-C full-proof ratio by 24.7-51.7 points over a code-only baseline.
- SpecSyn: LLM-based Synthesis and Refinement of Formal Specifications for Real-world Program Verification, arXiv 2026. arxiv.org/abs/2604.21570. 78.5% full proof on 1,365 real C targets across 7 repositories, via mutation-discrimination-guided refinement.
- LiveFMBench: Unveiling the Power and Limits of Agentic Workflows in Specification Generation, arXiv 2026. arxiv.org/abs/2605.01394. Contamination-controlled ACSL benchmark; pre-2025 pass@1 17.91% collapses to 2.99% on a fresh 2025 subset.

**Axis 4 crossover, Rocq/Coq and F* specific (critic gap, all extra round)**

- Graph2Tac: Online Representation Learning of Formal Math Concepts, arXiv 2024. arxiv.org/abs/2401.02949. Online GNN over a 520K-definition Coq mono-graph reaches 33.2% on a package-split holdout, beating CoqHammer's 17.4%.
- Clarifying Before Reasoning: A Coq Prover with Structural Context, arXiv 2025. arxiv.org/abs/2507.02541. Structured-context retrieval reaches 45.8% with DeepSeek-V3, 2.1x Graph2Tac's 33.2%.
- Planning to Hammer: Difficulty-Aware Decomposition for Automating Rocq Proofs (Quarry), arXiv 2026. arxiv.org/abs/2606.17981. Decompose-then-hammer reaches 55%/52%/16% across three benchmarks vs. a 48%/39%/3% baseline.
- What's in a Proof? Analyzing Expert Proof-Writing Processes in F* and Verus, arXiv 2025. arxiv.org/abs/2508.02733. Telemetry study: active-error count during proof authoring is the sharpest process-level predictor of success.

**Other 2026 reads used for corrections and context**

- MutDafny: A Mutation-Based Approach to Assess Dafny Specifications, ICSE 2026. arxiv.org/abs/2511.15403. 40 operators, 118,458 mutants over 794 programs, about 1 weak spec per 241 lines.
- Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles, arXiv 2026. arxiv.org/abs/2601.12845. The actual source of the 85.7%-vs-42.1% IDE user-study figures Lens A had misattributed to SpecCoder.
- Clover: Closed-Loop Verifiable Code Generation, arXiv 2023-2024. arxiv.org/abs/2310.17807. Six-way regenerate-and-compare consistency check; 0/240 false positives on an adversarial mutant suite.
- P3: Joint Program-and-Proof Planning for Verified Code Generation, arXiv 2026. arxiv.org/abs/2608.09277. Joint planning beats implementation-only planning by 3.3-8.3 points across Verina/AlgoVeri/Lean4Commit0.

## Method

Three lenses were run: A (the frontier map, a broad literature sweep),
B (t's own numbers placed against lens A's, axis by axis), and C (a ranked
list of moves with evidence, effect and first hurdle). A critic pass then
read lens A alone and flagged eight specific gaps in coverage (no dedicated
SPARK or Frama-C automation source, no dedicated Rocq or F* frontier
source, contemporaneous Lean provers DeepSeek-Prover-V2 and Kimina-Prover
missing as named systems, no cost/compute-efficiency axis, no pre-LLM
deployment baseline, no classical (non-LLM) vacuity/mutation literature, no
leaderboard-currency check, and a SPARK proof-success axis with literally
no number anywhere) plus eight specific unverified claims inside lens A's
own text.

Counts: raw candidates 191, distinct titles 150, read in the first pass 60,
kept after the critic's extra round and a second independent fetch-and-check
pass on nearly every claim 80, dropped by the skeptics' verification (wrong
paper, unconfirmed figure, or genuinely not found) about 20 (unwitnessed:
these pipeline counts appear only in this prose; no external log or table
records them).

The extra round answered all eight of the critic's coverage gaps directly:
SPARK and Frama-C automation is covered by seven dedicated 2026 reads (The
Prover Is the Judge, Marmaragan, AutoACSL, SpecSyn, LiveFMBench, CASP,
AutoDeduct, and the Contract-Based-Verification-of-NFRs paper), giving a
concrete SPARK LLM-automation number (Marmaragan's 50.7%) where the critic
correctly noted none existed; Rocq and F* are covered by Graph2Tac,
Clarifying Before Reasoning, Quarry, PROVE-RT and the F*/Verus telemetry
study; DeepSeek-Prover-V2 and Kimina-Prover turned out to already be present
throughout the corpus as named baselines in Goedel-Prover-V2, Seed-Prover
and BFS-Prover, just not surfaced as their own top-level entries; a
cost/compute axis was built directly from VeruSyn's, AutoVerus's and Vero's
own reported dollar figures, spanning about $0.17 to $67-100+ per task; the
pre-LLM deployment baseline came from the SPARK Wikipedia article and
AdaCore's own quality-assurance documentation; the classical vacuity/mutation
lineage turned out to already be named in t/RELATED-WORK.md's own gap
analysis (Beer et al. 2001, mutation-based vacuity 2010) rather than needing
a fresh search; and the SPARK-axis-with-no-number gap is the same one
Marmaragan's 50.7% answers.

The leaderboard-currency check was not run as a fresh, dated search; the
survey instead cross-checked each headline number against every other
paper in the corpus that cites the same benchmark (for example
Seed-Prover's MiniF2F 99.6% is checked against Goedel-Prover-V2's 84.6%/8B
and BFS-Prover's 72.95%/7B, all internally consistent as of each paper's own
publication date), which establishes relative standing within this corpus
but does not confirm any single number is still state of the art as of
2026-09-09 on an external leaderboard.

Of the eight specific unverified claims the critic named in lens A's own
text, the extra round's independent re-fetches resolved six as confirmed
and one as a genuine error, with one remaining only partially resolved:

- DriftBench/BPF attributed to "The Faithfulness Gap" (2606.16541), possibly
  conflated with "Fidelity Probes" (2605.17246): **not conflated.** Both
  papers are real and distinct; the Faithfulness Gap's own numbers (89.6%,
  F1=0.91) were independently confirmed against its full text, and Fidelity
  Probes is a different system entirely (COBOL/EARS, not DriftBench).
- "Tan's MIT thesis" attributed to 2605.30914 with no author/institution in
  the source list: **confirmed.** The paper's own metadata states MIT
  Master of Engineering, EECS, advised by Max Tegmark.
- Venue attributions for CLEVER (NeurIPS 2025), AlgoVeri (ICML 2026),
  AutoVerus (OOPSLA 2025), KVerus (ASE 2026), Re:Form (TMLR): **confirmed**
  from each paper's own front matter. Vericoding's "POPL 2026" attribution
  **remains sourced only to t/RELATED-WORK.md**, not independently
  confirmed from the paper itself.
- AlphaProof's ~1M-to-~80M-statement auto-formalizer figure stacked on the
  same source as its 500-TPU-day figure: **confirmed**, both numbers are
  stated directly in the Nature paper, not inferred or stacked from
  outside knowledge.
- "VeruSyn" as the system name for 2602.04910's 6.9M-program corpus:
  **confirmed**, the paper's own text names the system VeruSyn.
- Vero's "GPT-5.5 xhigh" model identifier: **confirmed** as the paper's own
  stated effort-level label.
- Lean Kernel Arena's 19 checkers and its regression-catching claim:
  **confirmed** by direct fetch; 19 checkers, and an older official Lean
  release does show real soundness failures against the current suite. Some
  of the per-checker sub-details in the first pass's reading of the table
  (specific soundness/completeness counts for individual named checkers)
  were themselves wrong and corrected in the extra round.
- SpecCoder's "85.7% vs. 42.1%" IDE user study: **refuted as attributed.**
  Those figures belong to a different paper entirely, "Automatic Generation
  of Formal Specification and Verification Annotations Using LLMs and Test
  Oracles" (arXiv 2601.12845), whose own IDE study (a VS Code "Dafny AI
  Assistant" extension) reports exactly those numbers. SpecCoder
  (2607.04232) has no IDE study; this was lens A's one clear citation error
  among the eight flagged claims.

A fourth pass, run 2026-09-10, verified "The moves" section itself: each of
the 14 ranked moves was checked by two independent skeptics, one against its
cited source and number, one against t's own measured state. Of the 14
moves, 1 was kept as written, 12 were corrected (an evidence citation,
number, expected effect or first hurdle needed restating, most often
because the cited source was confounded, mislabeled or misattributed, or
because the effect targeted the wrong t instrument), and 1 was dropped
because a skeptic showed with direct evidence (a grep of t/verifiers/*.py)
that the build it proposed already exists in the repo. None of the 14 were
left marked unverified; every move resolved to keep, correct or drop on the
evidence gathered.
