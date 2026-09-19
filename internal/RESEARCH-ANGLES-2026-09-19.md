# Research archive recovered; candidate change in learning strategy

## What was actually retrieved and reviewed

The complete existing lab report archive was copied into `tup-reports/`: 885
files, 584,478,642 bytes. All 885 local files match the source SHA-256 manifest.
It includes 306 PDF copies in the paper collections, representing 164 distinct
PDF contents by hash. Including reports and talks gives 313 PDF copies and 171
distinct contents. All 171 extracted successfully on the lab. The archive was
preserved, including duplicate copies, source pages and old indexes.

The local [searchable index](../t/out/research-review-2026-09-19/INDEX.md),
[catalog](../t/out/research-review-2026-09-19/catalog.json), and
[checksums](../t/out/research-review-2026-09-19/SHA256SUMS) cover the full set.
Every arXiv reference in the old indexes has a local PDF. The 136 index rows
without a PDF include websites, repositories and publisher metadata; they are
not 136 missing papers. Old index labels are retained as labels, not assumed
independent identity checks. The archive is ignored local material, not a
redistribution of third-party papers through the public Git repository.

This is an initial targeted review, not a claim to have read every paper. The
abstracts and selected methods/setup passages of the eight papers below were
read from the actual extracted PDFs. AlphaVerus, FoVer and Goedel-Prover-V2
metadata were also checked against their primary arXiv pages. The archive is
heavily weighted toward formal verification; it is not a complete literature
search on small-model pretraining or architecture.

## The central hypothesis

Our distinctive resource is executable semantics plus several proof backends.
The current owned-core pilot uses those resources indirectly: it learns next
tokens from raw source, documentation, tests and proofs. The older supervised
pipeline mostly keeps successful complete answers. Neither objective directly
teaches a small model which semantic step to take, where a candidate first went
wrong, or how to choose a useful subgoal.

The candidate angle is **a small learned guide operating over checkable t
states, trained on dense semantic feedback and a generated curriculum**. Use
symbolic execution/proving/search to do work that does not need to be stored
in weights, then teach the model to choose productive actions. This is an
inference from the papers and our pipeline, not a demonstrated locallm result.
It does not establish general Phi-level ability or make extra search free.

## Relevant mechanisms and their limits

| Paper | Mechanism relevant here | Important limit |
|---|---|---|
| [FoVer](https://arxiv.org/abs/2505.15960v3) | Formal tools label individual reasoning steps, providing process supervision without a model grading its own answers. | Its experiments fine-tune 7B/8B pretrained reward models; transfer to a 91M model from random initialization is unproved. |
| [AlphaVerus](https://arxiv.org/abs/2412.06176v1) | Translate existing programs, branch over verifier-guided refinements, and filter specification/program misalignment. | Uses a capable 70B pretrained generator and inference-time search; not evidence that a tiny untrained generator can bootstrap itself. |
| [Goedel-Prover-V2](https://arxiv.org/abs/2508.03613v1) | Increasing-difficulty synthetic tasks, training for verifier-guided correction, and checkpoint averaging to maintain diversity. | Published small models are still billions of parameters; correctness benchmarks and candidate budgets matter. |
| [STP](https://arxiv.org/abs/2502.00212) | Conjectures are selected near the current prover's solvable frontier, addressing sparse successful-proof training data. | The reported Lean experiment generated 51.3 billion tokens. We should test the curriculum mechanism cheaply, not assume its scale is available for free. |
| [Absolute Zero](https://arxiv.org/abs/2505.03335v3) | Self-proposed code reasoning tasks are checked by an executor, with task selection driven by learning progress. | Algorithm 1 explicitly requires a pretrained base model; “zero data” does not mean zero pretraining or random weights. |
| [rStar-Math](https://arxiv.org/abs/2501.04519v1) | Code-assisted reasoning trajectories, tree search and a learned process preference model improve task-specific reasoning. | Starts from pretrained models and uses substantial generated traces/search; its math scores cannot be transferred to t or our model. |
| [DeepSeek-Prover-V2](https://arxiv.org/abs/2504.21801v2) | Break difficult statements into subgoals and construct verified intermediate training material. | The cold-start pipeline uses a strong teacher. Any teacher-assisted gain must be identified as such. |
| [Graph2Tac](https://arxiv.org/abs/2401.02949v3) | Structured representations and online access to nearby definitions/proofs reduce reliance on a fixed offline text model. | Coq theorem proving is a different task. This motivates a retrieval/structured-state ablation, not a claim that a new graph model is automatically better. |

## Why this is not simply retrying an old failed idea

The handoff records 110 self-repaired answers with only two clean successes,
versus a much better fresh-sample yield. It also records unchanged clean counts
after more answers and proof-targeted preference pairs. Those failures remain
valid. We should not rerun a whole-answer rewrite loop with vague verdicts and
call it a new strategy.

The changed variables would be: immutable contracts; independently checked
intermediate subgoals or execution states; explicitly localized mistakes;
typed candidate actions; and training on those transitions before testing
bounded search. An unresolved proof obligation is neither a verified step nor
a semantic failure. A timeout is not a negative correctness label. No model
may edit a contract, checker, held-out test or acceptance gate to obtain reward.

## A bounded experiment before another broad expansion

Finish the active 4000-step matched study unchanged. Then use the same owned
modern checkpoint as initialization for paired interventions:

1. Build a small deterministic curriculum of t programs with scalar, branching,
   sequence and loop families. Generate state transitions, executable examples,
   and controlled semantic mutations. Keep interpreter-derived labels distinct
   from independently proved obligations; validate the generator against a
   separate reference implementation and reserve entire families for evaluation.
2. Compare final-answer-only training with intermediate-state/action training
   under matched model, token budget and seeds. Give the control equally valid
   final examples; do not confound the result with more training tokens.
3. Evaluate single-candidate correctness first. Separately compare fixed-budget
   candidate sampling against structured search with the same total generated
   tokens, verifier calls and wall-time caps. Keep all seven real/twin checks
   and current spec alignment for the final acceptance metric.
4. Only add a task-generating self-play loop after the model reliably solves
   the easiest curriculum. Otherwise it will manufacture mostly unusable data.

Proposed falsification target, to freeze before collecting this experiment's
data: at least a five-percentage-point improvement in held-out executable
correctness for state/action training over the final-only control under equal
tokens, without reduced final proof/spec acceptance. Also require a measured
increase in fully accepted solutions per fixed search budget before adopting
search as the product path. These are proposed tests, not achieved outcomes.

The immediate research lesson is about the training signal and the division of
work between model and tools. The completed architecture comparison establishes
lower token loss, while its repetitive completions show why that metric cannot
decide this next experiment by itself.

## Online follow-up: evidence closer to our scale

Primary full-text review on 2026-09-19 changes the priority of the search.
The following are candidate mechanisms, not measured locallm improvements.

**ExeDec, [version 2](https://arxiv.org/html/2307.13883v2), is the strongest
new lead.** Its experiments include transformers trained from scratch on
generated DSL tasks. It predicts intermediate execution results, synthesizes
a subprogram to reach them, executes it, and continues with the resulting
state. It compares against both whole-program generation and a stepwise
method without explicit subgoals. Five training initializations and distinct
compositional splits make this more relevant than a pretrained-model anecdote.
The subgoal intervention is not uniformly best: the no-subgoal variant wins
on DeepCoder's training distribution and length generalization. Its two-model
architecture and search add costs that our comparison must account for.

Application: add a third arm to the proposed experiment—stepwise code with
execution feedback but no predicted subgoal. This distinguishes the value of
decomposition from the value of predicting states. Hold out operation order,
combinations and program depth, not merely new numerical examples. Preserve
the original t contract throughout; execution examples do not replace proof.

**Cadmus, [version 1](https://arxiv.org/html/2602.09112v1), supports testing
executable synthetic curricula with a compact instruction vocabulary.** Its
reported model has 280M parameters and a 65-token VM vocabulary, trained on
80M sampled programs. Perfect comparison results inside the training range
coexist with roughly 46% accuracy on unseen-value equality cases. This is
evidence for measuring extrapolation separately, not general superiority over
large models. The abstract's under-$200 claim is not our budget estimate:
the methods also specify 300,000 steps, batch 1024 and eight H100s, without
enough information here to reconcile the cost. The article says the framework
will be released; availability has not been verified.

Application: test instruction-aware tokenization and verified program
curricula separately. Do not change vocabulary and learning objective together
and attribute any gain to either one.

**[TRM](https://arxiv.org/html/2510.04871v1)** supplies a core architecture
candidate: repeatedly refine a latent state and answer, with supervision
across refinement steps. Its puzzle setting is not an autoregressive language
model replacement. A fixed-shape t state predictor is a more defensible first
test than replacing our entire decoder on the strength of ARC scores.
**[Recurrent-depth language modeling](https://arxiv.org/abs/2502.05171v2)**
provides a language-model counterpart, but its reported 3.5B-parameter,
800B-token setup does not establish efficiency at our scale. Equal parameters
alone would unfairly ignore the extra recurrent computation.

Next evidence to obtain: ExeDec model sizes, training/search budgets and
released implementation; additional work on execution supervision and
learned library reuse. Then freeze a feasible ablation before generating its
evaluation data. No new method has yet earned adoption or a breakthrough claim.

## Combining mechanisms rather than selecting a single paper

Two more primary sources supply complementary mechanisms:

- [DreamCoder, PLDI 2021](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)
  learns reusable library abstractions alongside a neural search policy. Its
  comparisons distinguish refactoring from simply memorizing whole solutions.
  For t, this suggests mining repeated typed fragments into helpers, then
  teaching their composition. Every proposed helper still needs its own
  semantics checks; compression is not evidence of correctness.
- [CodeIt, version 2](https://arxiv.org/html/2402.04858v2) learns from what a
  sampled program actually computes using hindsight relabeling and prioritized
  replay. The main model is pretrained CodeT5+ 220M. Its random-initialization
  ablation eventually improves, but Table 2 reports only 9/400 policy-only
  successes versus 35/400 cumulative successes. Search history and improved
  weights are different outcomes. For us, relabeled executions may become new
  synthetic tasks with new identities; they must never overwrite an original
  problem's contract or count as solving it. Replay can preserve useful
  transitions even when a complete solution fails.

The proposed combination is a closed training cycle:

1. Generate independently checked programs and executions (Cadmus motivation).
2. Train locallm to propose intermediate states and code reaching them (ExeDec).
3. Execute candidate steps and retain valid transitions, including useful
   transitions from unsuccessful attempts (CodeIt-inspired replay).
4. Mine reusable, checked helpers from training solutions (DreamCoder).
5. Test recurrent computation inside the state predictor (TRM-inspired), with
   a matched-compute nonrecurrent control.
6. Distill successful searches into the owned model, then measure its unaided
   performance as well as the full search system separately.

This is a proposed integration, not a claim of research novelty or evidence
that individually successful methods combine successfully. In particular,
subgoal errors can amplify recurrent mistakes, replay can favor trivial
behaviors, and helper mining can leak evaluation solutions unless isolated.

### Interaction tests to preserve

Use a 2-by-2 comparison of explicit subgoal prediction and prioritized
transition replay, with stepwise execution available in all four cells.
Keep a whole-program reference outside this factorial. The interaction is
the combined gain minus the sum of the two individual gains, computed using
paired training seeds on identical sealed task families. Report the actual
cell scores even if the interaction is negative. Match training token budgets
and report GPU time; bound search tokens, executions and wall time separately.

Next test helper reuse crossed with recurrent refinement using the same
discipline. Do not require each component to win alone before trying its
predeclared combination: synergy is precisely what an interaction test checks.
The exact training schedule, model sizes, data generator and evaluation split
remain to be frozen; this section is a design direction, not a launch-ready
preregistration. A gain on generated tasks must subsequently survive the
original seven-verifier/twin/spec acceptance evaluation.

Reproducibility follow-up: ExeDec's [official implementation](https://github.com/google-deepmind/exedec)
is available. Appendix E reports 3-layer models, width 512, feed-forward width
1024, 4 heads, batch 128 and 500,000 steps with fresh synthetic examples.
Its reported accelerator setup must not be mistaken for our training budget.

## Direct evidence for interacting methods: symbolic traces plus reasoning

[Teaching LLMs Program Semantics via Symbolic Execution Traces, v1](https://arxiv.org/html/2605.06184v1)
is particularly relevant to the requested combination. Qwen3-8B violation
detection scores are 49.4% baseline, 48.0% with thinking, 56.7% with curated
trace training, and 67.3% with both. Their difference-in-differences is +12.0
percentage points. The +17.9-point headline is the combined change against
the non-thinking baseline, not the interaction itself.

The evidence has limits: binary C-property verdicts, one pretrained model,
no downstream proof-generation evaluation, and no contamination assessment.
The overall improvement is only +2.7 points; holds accuracy suffers from
output-budget exhaustion. Excluding unparseable responses would hide that
operational cost. Training on all traces hurt; source-only training also hurt.
Size comparisons change trace composition, so they do not isolate size.
Structured reports worked better than natural-language rewrites in this setup.

Application: retain path conditions, state transitions, error locations and
witness provenance as structured records. Test curated failure traces crossed
with bounded refinement, scoring every attempted task including truncations.
Do not equate an observed failing input with a universally failing program,
or an incomplete analysis with a proved-safe program. This is a new candidate
factorial, not proof of transfer to our 91M owned core.

### Implementation interface identified in the current repository

`t/interp.py:exec_body` already accepts a hook; inspect its precise event
semantics before adding a new tracing mechanism. Concrete traces from this
hook can support an execution curriculum, but symbolic path conditions need
a separate checked producer. Keep their evidence types distinct in the data
schema: concrete execution, satisfiable counterexample, proved obligation,
unknown, and timeout. For each transition retain the original task and
contract hashes, operation location, pre/post state, input, producer version,
and independent validation status. This prevents replay and helper mining from
silently promoting a bounded execution result into a proof label.

Inspection found an important limitation: the existing hook fires before
entering a while loop, not after each statement and not on every loop
iteration, despite its arrival-oriented docstring. It is insufficient for
transition supervision as written. A dedicated opt-in event interface with
stable AST locations and copied pre/post snapshots is needed, followed by
tests covering repeated iterations, nested branches and early returns.

Next implementation step is a trace-export adapter and independent reference
checks on a development-only program set. It must not alter the running
training study or consume the sealed semantic evaluation families. This gives
the subgoal, replay and refinement experiments a shared auditable data source.

Implementation progress: `interp.exec_body(..., trace=callback)` now emits
copied entry/exit states and branch/loop-guard events at stable AST paths.
Existing loop hooks retain their behavior. Three lab tests in
`t/test_execution_trace.py` pass: loop states against Python sums over 23
inputs (also matching untraced state and step counts), nested early returns,
and undefined-expression failure without a success event. Snapshot aliasing
is checked. This interface is concrete telemetry only; helper/function bodies
inside expressions remain opaque. Dataset export, independent validation of
additional operation families and the training comparison remain unfinished.

`t/execution_trace.py` now exports bounded concrete records with task/contract
hashes, interpreter/exporter hashes, typed snapshots, event limits, and
distinct precondition/undefined/budget/postcondition outcomes. Records default
to independently unvalidated and ineligible for training. Scalar and sequence
values are supported; other values fail explicitly. Three lab exporter tests
pass, including twenty independent arithmetic outcomes, changed-contract
identity, JSON round trips, and budget/precondition/type distinctions. The
earlier witness and inline-helper regression scripts passed 8 and 12 checks.
This is an API prototype, not a finished corpus or an adopted learning method.

## Transfer audit: do execution gains improve the generator itself?

[CodeExecutor](https://arxiv.org/html/2305.05383v1) reports a HumanEval gain,
but its downstream setup generates 200 candidates with Codex and ranks them
using predicted executions before evaluating 50. This is evidence for
candidate selection, not evidence that execution pretraining improves that
generator's unaided pass@1. Since t already has a cheap executable interpreter,
replacing real execution with an approximate model is not an obvious win.
The paper also explicitly reports faithfulness failures on complex programs.

[Self-Execution Simulation Improves Coding Models](https://arxiv.org/html/2604.03253v1)
combines execution SFT, output-prediction RL and coding objectives, then uses
simulation for selection and iterative repair. Its bases include Qwen2.5 3B/7B
and CWM, with a large teacher-assisted trace collection. This supports testing
joint objectives but does not establish transfer at our scratch-trained scale.
Its natural-language trace recipe differs from the symbolic-trace paper's
finding that informalization hurt; the tasks and training setups also differ.
There is no universal winning trace format established by these two studies.

Design consequence: evaluate three distinct outcomes on the same locked
families: (1) unaided one-candidate synthesis, (2) exact-execution-guided search,
and (3) learned-subgoal-guided search with exact checks. Count every generated
candidate and tool call. A reranking win cannot be called a core-model gain.
Preserve raw structured traces as the source of truth; derive any compact or
textual training representation deterministically and compare under the same
budget. Do not pay a teacher to narrate millions of traces before establishing
that our core benefits from a small checked structured curriculum.

Development corpus produced on the lab with `t/build_trace_pilot.py`:
`t/out/trace-pilot-2026-09-19-v2`, 735 records, 245 each for affine arithmetic,
absolute-offset branches and triangular-sum loops. Every final output matches
an independent Python formula; loop-header sums also match a closed form.
The corpus SHA-256 is
`23df3c1fc0629d601c422e300f171c8eefed3af0415d2f8541db1dc4bc236151`.
It is development-only, has no formal proofs or sealed evaluation split, and
remains training-ineligible. Four exporter tests pass. The first version is
retained; v2 explicitly labels missing postconditions rather than treating
their vacuous conjunction as a successful postcondition check.

## Auxiliary core objectives: useful candidate, adverse scale evidence

[Multi-token prediction, v1](https://arxiv.org/html/2404.19737v1) trains a
shared trunk with heads for several future tokens, retaining ordinary
next-token decoding. This is relevant to improving the weights themselves.
However, Figure 3 reports worse code performance for smaller models; benefits
grow with scale. Its small synthetic induction/arithmetic results are more
encouraging, but some experiments use test-selected stopping, and code
evaluations select oracle temperatures. These choices should not enter our
sealed comparison. Parameter matching reallocates trunk layers into heads;
it is not simply adding free capacity. Table S5 reports 1.22x training time
for four-token prediction at 0.3B despite the abstract's no-overhead framing.

Decision: retain two-token prediction as a secondary experimental factor,
not the default next core upgrade. Compare it crossed with execution-state
supervision only after the data/evaluation pipeline is ready. Record trunk
and head parameters separately, supervise no target across a document or
example boundary, and use both token-matched and measured-compute reporting.
A trace-curriculum interaction might differ from raw-code results; that is a
hypothesis to test, not grounds to ignore the adverse small-model evidence.

Additional leads opened but not yet method-audited:
[TracePile](https://arxiv.org/html/2510.23629v1) for transfer beyond execution,
and [Hierarchical Latent Prediction](https://www.microsoft.com/en-us/research/publication/hierarchical-latent-prediction-for-language-models/)
for multi-step latent objectives. Neither has been adopted on abstract claims.

TracePile methods audit: its 2.6M examples comprise about 19B tokens, with
experiments on pretrained 7B/8B models and 16 H800s. It reports downstream
reasoning and generation, but Table 3 contains regressions too: Qwen2.5-7B
LiveCodeBench falls from 25.8 to 23.5, while its CRUX rises from 46.5 to 49.4.
Thus execution accuracy cannot substitute for generation evaluation. Our
initial comparison should retain identical synthesis supervision in every
arm and vary the auxiliary execution signal, reporting both metrics. This
avoids interpreting mere exposure to an instruction format as semantic
transfer. Reference: [TracePile methods and Table 3](https://arxiv.org/html/2510.23629v1).

Training integration check: the owned core's `GPT.forward` uses
`ignore_index=-1`, not the common external-trainer value `-100`. Any SFT
adapter must translate its mask to the actual core convention and check the
decoded supervised tokens. Do not modify the frozen active study to change
this convention; implement the adapter against its existing interface.

HiLP full-text audit: [version 1](https://arxiv.org/html/2608.05806v1) combines
next-token loss with short- and longer-horizon latent consistency objectives.
Auxiliary modules are removed for ordinary inference. Its 1B models train on
100B tokens; HumanEval pass@1 is 8.77 for next-token training and 11.33 for
HiLP. This is closer to the requested core improvement than a reranker, but
still far above our training scale and not a replicated locallm result.
Stop-gradient placement is part of the method, not an implementation detail
that can be casually omitted.

New combined hypothesis: pair an auxiliary latent transition objective with
checked execution-state prediction, so the internal representation learns
both future context and program semantics while the deployed decoder remains
ordinary autoregressive locallm. Test four cells (neither, latent only,
execution only, both) from the same initialization with identical synthesis
examples. This combines HiLP's training-only intervention with execution
supervision; it is an adaptation, not a faithful reproduction or a demonstrated
novelty. Predicting future latents must use detached targets and causal inputs;
true future tokens/states must never leak into the synthesis inference path.
The existing source study remains frozen while this experiment is prepared.

Core-objective prototype: `locallm/latent_objective.py` implements detached
future-state prediction at configurable horizons. It is deliberately labeled
an adaptation, not HiLP: hierarchical aggregation, KL and the combined head
are absent. Four CPU lab tests pass, including stop-gradient targets,
example/padding boundary exclusion, empty-horizon gradients, and integration
with the owned modern core. The auxiliary gradient reaches backbone weights
while logits are unchanged by observation hooks. Normal next-token loss must
remain active to resist collapsed representations. No training study or
quality comparison has used this prototype yet. The active model and runner
files have not been changed.

HiLP Appendix C changes the cost assessment: its training throughput is
81,653 versus 126,278 tokens/s/GPU for the next-token baseline, about 65%.
Equal token counts therefore do not mean equal compute. Appendix A also
conditions lower-level transitions on teacher-forced next-token embeddings;
our current prototype does not. Keep it named `FutureStateObjective`, not
NextLat or HiLP, and test whether unconditional future prediction is useful
before drawing conclusions about those published methods.

The 12 version-pinned arXiv papers from this online follow-up have now been
downloaded and extracted on the lab, then mirrored locally under
`tup-reports/papers/followup-2026-09-19/`. Its `manifest.json` records source
URLs, PDF byte counts, PDF SHA-256 and extracted-text SHA-256. All 12 downloads
passed PDF-header and text-extraction checks. These are additions to the
original archive inventory, not included in its earlier 885-file count.

Training adapter: `locallm/completion_batch.py` encodes the exact inference
prompt separately from its completion, applies the core's -1 ignore mask,
shifts causal targets, refuses truncation and keeps one example per sequence.
Three lab tests check shifts, Unicode, zero prompt/padding loss gradients and
overflow rejection. Five examples were also decoded with the frozen source
BPE: only the intended completions were supervised. This is not a completed
dataset audit; no packing is used and no research training has launched.

Development trace validation strengthened: `t/pilot_trace_reference.py`
constructs expected states and control-flow events from independent Python
closed forms, without interpreting ASTs or importing `interp`. All events and
final values match for 735 regenerated records in
`t/out/trace-pilot-2026-09-19-v3` (SHA-256
`7473aa05f3c4a72dfaf2dbbf3721ff1e38b7abdec992cb57a2a51a23afcdd705`).
Deliberately corrupted state values, AST locations and missing events are
rejected. These three template families are now independently checked concrete
telemetry; that does not establish proof validity or out-of-family correctness.
Training eligibility remains false pending an actual split and dataset audit.

## NextLat: stronger scale match; revise the prototype priority

[NextLat v1](https://arxiv.org/html/2511.05963v1) includes a 57M inference-model
TinyStories experiment, with 66M total training parameters. One-step training
runs at 3.26 versus 3.72 iterations/s for GPT; eight-step training falls to
1.89. Its future-token probe results support studying representations, not
claiming an existing program-synthesis gain. This is nevertheless a closer
scale match than HiLP's 1B experiment.

Appendix C specifies a layer-normalized concatenation of current state and
next-token embedding, a three-layer GELU MLP predicting a residual update,
detached future-state regression targets, and an output-distribution KL term
through a detached output head. Recursive rollouts reuse the transition model.
The displayed pseudocode has apparent naming/dimension inconsistencies;
implement from the equations and validate against a hand-computed case rather
than copying it literally.

Priority revision: implement and test this token-conditioned objective before
using the unconditional `FutureStateObjective` as the main latent arm. Keep
the latter as an explicitly different ablation. Cross the faithful latent
objective with checked execution supervision and score unaided synthesis.
Report auxiliary parameter and measured training costs; no inference search
is necessary for this first core comparison.

`locallm/next_latent.py` now implements the token-conditioned residual
transition, recursive rollout, detached-state SmoothL1 and detached-output-head
KL losses. It excludes synthetic initial-state transitions and masks every
interval crossing an example or padding boundary. Three CPU lab tests pass:
losses match explicit numerical calculations, targets/output weights receive
no auxiliary gradient, token embeddings receive the expected gradient, and
empty/boundary cases remain finite. The MLP widths and initial-state exclusion
are recorded implementation choices; no exact paper reproduction is claimed.
This replaces the unconditional prototype as the intended latent training arm.
No GPU quality experiment has run with either objective yet.

Training integration: `locallm/research_model.py` wraps the unchanged core,
captures causal hidden states/token embeddings, and adds the optional NextLat
loss. Three CPU lab checks passed: the disabled path exactly matches baseline
logits/loss/gradients; an enabled optimizer step has finite gradients and its
core-only checkpoint reloads with identical logits; supervised padding is
rejected. Hooks are removed after each forward. The wrapper's full state is
needed for training resume; its core-only export is for ordinary inference.
Distributed training, memory throughput and held-out quality remain untested.

Factorial mask integration: `encode_segments` produces identical input IDs
across treatments while toggling intermediate-token supervision. The wrapper
accepts a separate, disjoint execution-target tensor and normalizes execution
loss separately, preserving the synthesis/final-answer loss weight. Four
batch tests and four wrapper tests pass on the lab, including identical
completion losses with execution supervision enabled and rejection of
overlapping targets. This avoids diluting synthesis loss merely by adding
longer supervised traces.
