# Dawnr after the current candidate: the next release cycle

Current runtime follow-up, October 30: the H100 attempt ended at its account's
billing spending limit. Its complete step-300 checkpoint has been recovered, and
a replacement L4 has passed cloud validation and resumed that checkpoint on the
other funded cloud account. The working goal retains the 24-hour VM bound and
$30 planning allowance while completing training and qualification. The detailed correction and next
actions are below. [Recovery registration](../release/evidence/parallel-seed2-billing-recovery-2026-10-30.json).

The earlier 90-minute continuation was designed only for the original eight-hour
function limit. It was prepared but never invoked and does not apply to this
billing termination. Its [controls](../release/evidence/parallel-seed2-continuation-2026-10-29.json)
remain preserved beside Modal's [resumable training example](https://modal.com/docs/examples/long-training).

Finish the registered two-seed candidate and its release decision first. The next
data experiment should make the internal Cohere teacher better at producing valid,
useful specifications. Test type and scope restrictions, then problem-matched
examples, as separate changes. Train again only when the resulting data merits a
new measured comparison. These are research proposals, with proposed spending
caps; no new allocation or provider run follows from this note.

The order below uses Dawnr's records first, then primary papers and current Cohere
documentation checked on 2026-10-29. The older plateau note contains superseded
base-row and local-compute assumptions; the current release plan governs those.
The documented local mirror command was unavailable, so the relevant papers were
read from their publishers or authors. Cohere remains internal to development and
training. Cloud GPUs handle training/decoding, GitHub handles full grading, and
the local machines handle final product tests.

The most useful facts from our own measurements are:

- JSON-v2 converted 142 of 500 replies but kept only two strict problems, both
  already covered: zero added rows for $11.410546 recorded. The paired follow-up
  then lost 52 of 70 replies at static checking and added zero rows in either arm.
  Repeating either unchanged recipe has no expansion case.
  [JSON result](../release/evidence/cohere-json-v2-pilot-result-2026-10-29.json),
  [feedback result](../release/evidence/cohere-static-feedback-result-2026-10-29.json).
- A read-only census of the frozen 6,954-row training input reproduced all 339
  distinct unparsed fenced blocks. Every one occurs only in a prompt; none occurs
  in a `chosen` target. Blanket removal would therefore discard input examples
  rather than fix malformed target syntax. This does not establish static
  validity, intended meaning, or full contamination coverage.
  [Census](../release/evidence/training-parse-roles-2026-10-29.json),
  [reproduction script](../t/recipes/row_parse_roles.py).
- The current dataset already contains 525 specification-repair rows: 498 from
  visible-test failures and 27 from reference failures. Repair training is already
  part of this candidate, and needs a measured reading before another expansion.
  [Census](../release/evidence/training-parse-roles-2026-10-29.json),
  [existing builder](../t/recipes/v10_repair_rows.py).

Use the completed candidate's development funnel to choose the next action:

| Observed result | Next action |
|---|---|
| All release conditions pass | Ship the selected weights, preserve that baseline, then start the first small teacher experiment below. |
| Static or specification coverage remains the main loss | Run the type/scope pilot, followed by the retrieval comparison if justified. |
| Specification precision fails | Investigate surviving wrong specifications and strengthen training-side counterexamples before adding volume. |
| Specifications pass but implementations or proofs fail | Measure the already-trained repair skill at equal request budget; use the failing stage to select new traces. |
| Quality holds but the laptop condition fails | Profile startup, generation and proof time separately, then fix the measured cost. |

A failed candidate leaves the published weights in place. The current held-out
182 remains a single final reading after the existing selection decision, never a
source of repair prompts or a way to choose the other seed.

**First: restrict the teacher's type and scope choices.** JSON-v2 fixed operand
shape; it still lets the teacher choose incompatible types or unavailable names.
Start with a deliberately bounded contract fragment and generate its schema from
the problem's signature: separate expression categories by result type, enumerate
in-scope names and supported helpers, and let deterministic code assemble the AST.
Unsupported constructs count as coverage losses. Keep static, round-trip,
reference and both mutant-family checks unchanged.

[Type-Constrained Code Generation](https://arxiv.org/abs/2504.09246) supports the
mechanism: enforcing type constraints reduced compilation errors in its
TypeScript experiments. The
[authors' implementation](https://github.com/eth-sri/type-constrained-code-generation)
uses a completion engine and currently handles TypeScript. It is not a ready-made
Cohere integration. Adapting the idea through bounded schemas and checked choices
is our hypothesis; successful typing alone does not establish correct intent.

Cohere currently supports enums, nested objects and references, but omits schema
features including `minItems`, `maxItems`, `allOf` and `oneOf`. A capability probe
must validate the actual proposed schema before a yield trial. Keep arities in
required named fields and inspect the restored AST independently.
[Official schema support](https://docs.cohere.com/docs/structured-outputs).

Proposed first trial: freeze 50 uncovered training problems before new responses,
two candidates per problem in each of two arms, at most 200 logical requests.
Compare the typed construction with unchanged JSON-v2 on the same eligible cases;
report eligible cases against the whole frozen set as well. Reserve at most $25
of Cohere credit with a lower proxy ceiling and bounded in-flight requests.
Proposed expansion criteria: at least 90% static-valid completed outputs, at least
five newly covered problems with rows fitting the existing window, and at least
62 strict problems per $100 counting both arms' recorded cost. Require more paired
wins than losses and exact paired p <= 0.05 before claiming superiority. A small
pilot may be inconclusive; do not scale on syntax success alone. These proposed
criteria need an exact preregistration and input hashes before execution.

**Second: retrieve relevant examples for the teacher.** The current primer uses
the same six examples. Compare it with the same number and token budget of audited
training examples chosen by signature, operation family and problem description.
Keep the model, representation, output budget and checks fixed. Exclude evaluation
families and the target problem's own stored solution from the example bank.
Begin with deterministic structural retrieval; compare Cohere ranking only if
that leaves a measurable selection problem. The resulting prompt is used inside
the teacher pipeline.

[Synchromesh](https://www.microsoft.com/en-us/research/wp-content/uploads/2022/01/csd_arxiv.pdf)
combines target-aware example selection with semantic constraints and reports
complementary gains across its domains. This motivates the comparison, without
establishing a Dawnr gain. Give this separate pilot another proposed $25 ceiling;
expand only on additional strict, novel, fitting problems with complete costs and
a paired improvement. Reusing the first pilot's settings isolates retrieval's
contribution. Total initial teacher research allocation would be at most $50,
released one experiment at a time, not the whole remaining grant.

**Third: measure repair before adding more repair data.** After the current
candidate's decision, compare its existing repair route with equal-budget fresh
sampling on a newly frozen diagnostic split drawn from training-side problems.
Record repaired failures, regressions on initially correct answers, and unchanged
specifications. Use the existing witness builder; any new positive target must
pass the ordinary strict checks. A promising diagnostic still needs the full
development comparison and release conditions in a future registered experiment.

[CYCLE](https://arxiv.org/abs/2403.18746) provides evidence that explicit feedback
training can improve refinement in small code models. Our 525 existing traces
mean that the immediate question is whether their skill transfers to the route.
Proposed diagnostic compute cap: $10 of cloud budget, separate from Cohere credit,
with a hard time limit. Stop if repair does not beat resampling or damages correct
answers. Do not add inference calls merely because the repaired text looks better.

**If precision is the failure, use adversarial examples before RL.** Cohere can
propose difficult inputs and wrong outputs for training-side specifications;
independent execution determines their labels. Start from wrong specifications
that passed our present gate, retain the reference input/output and the rejected
mutant as an explicit example, and test the new counterexamples against known
correct specifications. The existing two mutant families already cover part of
this idea. The proposed addition must demonstrate new discrimination, not repeat
their score or change the current evaluation instrument silently.

[SpecRL](https://arxiv.org/html/2604.05820v2) rewards rejection of impossible
input/output pairs only after verification. Its ablation without verification
increased rejection scores while damaging verifiability. Its reported 7B run used
24 RTX 4090s for roughly 70 hours, about 1,680 GPU-hours. Copy the offline
counterexample lesson first; that training scale is not a demonstrated one-card
recipe. A separate
[Dafny RL study](https://arxiv.org/abs/2605.30914) also found specification hacking
before filtering weak tasks. Neither paper establishes a Dawnr gain or a cheap
RL implementation. Proposed counterexample pilot cap: $25 of Cohere credit, only
if the completed precision result makes it the chosen next experiment.

**Keep program-first curriculum generation as a reserve option.**
[SelfCodeAlign](https://arxiv.org/abs/2410.24198) derives tasks from code concepts
and filters generated solutions by execution;
[CodeRise](https://aclanthology.org/2026.findings-acl.1840/) uses syntax guidance
and progressive data generation for low-resource languages. A Dawnr adaptation
could start from audited, verified training programs and ask Cohere for grounded
problem descriptions and independently checked examples. However, our earlier
composition curriculum failed, and rewordings of one behavior are not new
coverage. A future pilot must test transfer to different program families and
check agreement between the description and its reference. This stays behind
the two smaller teacher changes; no full synthetic curriculum is proposed now.

Implementation order is concrete: finish the current artifact audits and release
decision, preserve the new baseline if it qualifies, choose one experiment from
the measured failure stage, register exact inputs and stop rules, then collect
and audit its result. A later training comparison changes one data intervention
with the base, recipe, seeds and decoding budget held fixed. All existing release
conditions still apply. Current Cohere model access, recorded charges and quotas
must be checked at execution time; grant balance alone does not establish model
capacity. The documented limits distinguish models and key types.
[Cohere limits](https://docs.cohere.com/docs/rate-limits).

One operational finding affects the current run and subsequent evaluation.
Google's runtime-limit procedure requires stopping and restarting an existing
VM to change its limit. The running candidate has a confirmed October 31 cutoff,
and its completed-bundle backups do not include every unfinished request cache.
Keep the training run intact and preserve its existing disk across VM deletion
using the separate disk auto-delete setting. That change is now verified, with
the original cutoff and live training process unchanged. Recover and verify the
needed model/cache evidence before deleting the retained disk; the working goal
now includes that cleanup and its seven-day review. This is a $5 storage planning
increment, not more GPU runtime or a new teacher trial.
[Runtime-limit documentation](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime),
[disk auto-delete controls](https://docs.cloud.google.com/compute/docs/disks/modify-persistent-disk),
[change receipt](../release/evidence/candidate-runtime-retention-2026-10-29.json).
# Runtime correction and next action, 2026-10-30

The second seed's saved log stopped at step 310. A result polling timeout was
insufficient evidence of live compute: direct provider inspection found its
container terminated at the account's billing-cycle spend limit. Modal documents
that spend limits can stop workloads independently of their function timeout
([budgets](https://modal.com/docs/guide/budgets)). This was a billing termination,
not the eight-hour runtime limit anticipated by the prepared continuation.

The complete checkpoint at step 300 was recovered with the original preparation,
training rows and state files. The original call and dedicated app were stopped
before replacement work. The next action in the working goal is a bounded L4
recovery on the other funded cloud account, with full cloud validation of the
same recorded packages and checkpoint state before training. The hardware change
is explicit; the seed, recipe, data and model qualification conditions stay fixed.
A replacement is allocated with a 24-hour cutoff and a $30 planning allowance.
The current model-release objective still requires the complete second seed,
development comparison, conditional final reading, laptop checks, publication
and cleanup. The cloud validation has now passed and advancing training is
observed. The automatic adapter collector has 13 passing controls; its next
milestone is the verified completed adapter, not another training launch.
[Registration](../release/evidence/parallel-seed2-billing-recovery-2026-10-30.json),
[observed recovery](../release/evidence/parallel-seed2-recovery-running-2026-10-30.json).
