# locallm + t: an enterprise product and a credible Phi win

Proposed requirements, not achieved results. The engineering roadmap of record remains
[ROADMAP-LOG.md](ROADMAP-LOG.md). The operator reports OpenAI Select partner status; this plan assumes
no endorsement, credits, special access, commercial rights, or distribution benefits from that statement.

**Build a small model we train, and a verification service around it, that completes useful enterprise
programming work more accurately and cheaply than Phi.** Round 7's 7B adaptation is an experiment and a
possible data teacher. It does not complete the owned-model, efficiency, or enterprise objectives.

## Starting evidence

[The recorded results](../t/out/score-r6.md) put the 1.5B students at 3 clean of 232, tied with Phi,
and 2 after specification checking. The 10.9M locallm reaches 2 clean, with 196–204 wrong-but-proven
answers. The prompted 7B prover reaches 6 clean; none of those models is a demonstrated enterprise winner.
The 232 problems are repeatedly inspected MBPP, with possible upstream pretraining contamination.
They remain a regression set, not the final generalization claim.

The useful existing assets are the seven lowerings, interpreter, CLI/library, language server, verdict
cache, and [426 twin/witness pairs](../t/twins/README.md). Their limitations matter: shared translations
can contain bugs, agreeing checkers are not seven independent measurements of intent, and a proof can
verify the wrong specification. Existing t lacks floats, heap objects, and concurrency. The present
small corpus and locallm's weak semantic accuracy both require work beyond another adapter round.

## First product and its expansion

Start with **private generation and verification of deterministic business-rule and data-transformation
functions** for a software team's integration platform: record validation, bounded integer calculations,
sequence filtering, routing rules, and format normalization. Deliver a proposed implementation, its
reviewable contract, regression tests, and a replayable evidence bundle in the customer's pull request.
An engineer approves the contract and merge. Unknown, timeout, unsupported, and failed remain visible.

This is a proposed customer wedge, not validated demand. The advantage to test is less engineering review
and debugging time for correct changes with inspectable evidence. Do not sell universal correctness.
Proof generation runs at build/review time; executing an approved function does not call seven provers.

Grow t from observed customer and corpus exclusions. First census records/maps, structured strings,
fixed-point/decimal operations, modular function calls, and richer sequence operations. Select the next
construct by useful held-out tasks unlocked and implementation cost. Each addition needs specified
semantics, interpreter behavior, lowering/conformance tests, and adversarial twin evidence. A backend
that cannot express it must abstain. General heap and concurrency support are separate major projects.

## What counts as beating Phi

Pin the existing `microsoft/Phi-4-mini-instruct` baseline by revision. Its publisher specifies 3.8B
parameters; the 7B prover is a larger teacher candidate, not a smaller-model result.
([Microsoft model card](https://huggingface.co/microsoft/Phi-4-mini-instruct),
[DeepSeek model card](https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2-7B), checked 2026-09-19.)
Do not generalize a win over that checkpoint to every Phi model or to general-purpose intelligence.

Create a private suite of **500 independently specified enterprise tasks across at least 50 task
families**, covering the first product and the next language extensions. Hold entire families out of
training and development; record author/source, rights, reference behavior, and hidden boundary tests.
Derive the final fixed sample size from a separate development pilot and a power calculation before
locking the suite; increase it if 500 cannot detect the proposed improvement. Retain MBPP and add a
separately held-out, rights-cleared real-code suite as secondary reports. Count unsupported tasks and
abstentions in the denominator; show family coverage separately.

| Claim | Required evidence before making it |
|---|---|
| Better useful output | On the locked enterprise suite, at least +10 percentage points in fully accepted first-attempt tasks over Phi using the same t contract/evidence pipeline; family-clustered 95% interval for the difference has lower bound above +5 points. |
| More than a notation advantage | Against Phi producing its native Python, our executable answers also improve hidden-test functional correctness by at least +5 points. Apply the same task requirements, input domain, time budget, and failure accounting; report this separately from proof-backed acceptance. |
| A trained-model gain | Compare the owned locallm with its previous checkpoint, and every adapted model with its unadapted base, on the same held-out tasks. Include Phi with a development-tuned prompt and equal tuning budget; report an equally trained Phi control where claiming a training-method advantage. |
| Reproducible gain | Three independent training seeds and prespecified stochastic inference replicates; publish every seed, not the best. Pair outcomes by task, cluster by family, and never count seeds or sampled answers as new independent tasks. A second operator replays evidence from a pinned checkout and manifest. |
| Smaller and cheaper | The owned deployment candidate has at most 1.5B parameters, at most 70% of Phi's measured peak serving memory, and at most 50% of its total compute cost per accepted task on the same hardware and workload. Report model bytes, CPU/GPU seconds, verifier cost, rejected attempts, and amortized training cost. |
| Usable turnaround | Proposed first-pilot targets: p95 candidate response under 10 seconds, p95 complete evidence under 120 seconds, cached unchanged verification under 1 second, measured at declared concurrency and input/output limits. All are unmeasured targets. |

Lock prompts, grammar availability, sample counts, stopping rules, budgets, quantization, hardware,
kernel revisions, and scoring before opening the final suite. Equal token limits alone do not equalize
different tokenizers: also report wall time, FLOPs where measurable, and output lengths. Prespecify one
primary comparison; report exploratory variants without turning them into the headline after the fact.
Zero observed false accepts is a release condition, not proof of zero failure probability; report the
sample size, family dependence, and uncertainty of every accuracy claim.

## Executable milestones

| Order | Deliverable | Done when |
|---|---|---|
| 1 — locallm core | Audit and modernize `locallm/model.py`, `train.py`, `data.py`: architecture, tokenization, sequence length, batching, resume, evaluation, and inference. | Compare against the current character model at equal compute. Add a configurable scaling ladder, initially roughly 30–100M and 300M parameters, then up to 1.5B only when held-out semantic accuracy improves. Report training throughput, memory, perplexity, and task success; a faster loss curve alone is insufficient. |
| 2 — t capability | Census real code and representative business rules for missing constructs; add the highest-value language feature through every layer. | A new construct has frozen semantics, executable interpreter behavior, round-trip tests, conformance probes, explicit backend refusals where necessary, and real/twin evidence. Measure previously excluded tasks it admits; no silent weakening to gain coverage. |
| 3 — data beyond nl | Rights-cleared code with contracts, real transformation/rule tasks, trace-based exercises, proof-preserving compositions, and independently authored specifications. | At least 1,000 distinct accepted training tasks across 100 families, with semantic/structural deduplication and family-disjoint development/final sets. Record unsupported constructs and add t features by measured coverage. Superficial renamings do not count toward the target. |
| 4 — repeatedly demonstrate learning | Freeze the enterprise suite and task-level acceptance ledger, then train the owned model on meaningful problem-to-program examples and traces; test verified twins as contrastive supervision. A stronger model may supply candidate data, which must pass independent checks. | Every acceptance requires matching hashes, an explicit successful specification check, the exact seven kernels, and real/twin/witness evidence. Missing/stale checks, duplicate kernels, timeouts, and corrupt artifacts fail closed. Preregister equal-token/equal-compute tests-only versus tests-plus-proofs/twins ablations; three seeds show a semantic gain on unseen families. If absent, change the identified cause rather than repeating an unchanged recipe. |
| 5 — package and measure | Python SDK, CLI/CI integration, asynchronous local API, isolated verifier workers, and evidence replay. | A new operator installs a pinned bundle, submits a task, polls/cancels it, verifies artifacts, restores after a crash, and reproduces results with outbound networking disabled. The benchmark reports the quality/cost/latency gates above. |
| 6 — paid pilot | One customer team, one workflow, one named buyer and engineering owner. | The pilot below meets its adoption, quality, time-saving, and deployment conditions; only then propose recurring deployment. |

**The highest-priority implementation after round 7 is locallm's core, followed by t capability, new data,
and repeated measured training.** Without changing locallm's learning capacity and inputs, a better 7B
teacher does not improve the owned product. Task-level scoring defects must still be repaired before
any resulting run earns an acceptance claim; a larger model can optimize a broken instrument or a
familiar toy benchmark. A 50-task enterprise development suite should guide these stages before the
final independent suite is locked. Run core work alongside the teacher experiment.
All experiment compute remains on the shared lab workstation, with resumable jobs and immediate yielding.

## Integration and operational requirements

Build on `t/tlib.py`, `t/cli.py`, and the existing language server. Proposed API: submit a versioned job,
read status/results, cancel, retrieve artifacts, and replay. Require idempotency keys, bounded queues,
resource/time limits, authentication, project-scoped access, and explicit terminal states. Sandboxed
reference execution and compiler/prover workers must have no unnecessary network or filesystem access.

The evidence schema includes task/contract/test/model/tokenizer/lowering hashes, exact tool versions,
generation settings and seeds, lineage/licenses, all seven verdicts, twin operator and witness, raw logs,
resource measurements, and the final decision with its reason. Sign release manifests and test tamper
detection. A runtime wrapper enforces the proved input domain; interpreter or exported-code equivalence
must be validated separately. A proof about t is not automatically a proof about arbitrary emitted Python.

Ship customer-managed Linux first, with pinned offline installation, rollback, backup, retention/deletion
controls, and redacted logs. Customer source, prompts, outputs, and weights stay inside that deployment by
default; external model calls require a separately selected and documented configuration. Customer data
must not enter shared training without explicit contractual rights. Document the trusted components and
the limits of each guarantee; do not claim certifications that have not been earned.

## First commercial validation

Recruitment and outreach require the operator's separate direction; none is initiated by this plan.
First validate with three engineering teams whether reviewing deterministic rule/transform changes is
a recurring, budgeted problem. Ask for real change volumes, review time, defect/rework history, supported
languages, deployment constraints, and willingness to provide a rights-cleared retrospective sample.
Stop or change the wedge if none will commit an engineering owner and representative tasks.

Propose a four-week paid evaluation for one willing team: 50 retrospective changes plus at least 20 new
changes in shadow mode. Establish the existing developer workflow and a tuned Phi workflow as baselines.
Randomize presentation order and blind model identity where practical. Measure correctness against
customer-approved requirements, accepted coverage, engineer minutes including contract review and rework,
end-to-end latency, compute cost, and installations/support hours.

Pilot gates: at least 60% of eligible changes accepted with complete evidence, zero observed incorrect
accepted changes, at least 30% lower median engineer time, all outputs reviewed before merge, and the
customer successfully replays five randomly selected bundles offline. Report every ineligible task and
its exclusion reason. A 70-change pilot validates usability and demand; it cannot replace the larger
statistical comparison or establish a rare-defect guarantee.

Use a fixed scoped pilot fee, then negotiate an annual customer-managed deployment/support license from
measured value. Before quoting, require conservative verified monthly engineering savings of at least
three times the proposed monthly license equivalent, with support and compute included in our margin
calculation. No market-size or revenue forecast is justified yet.

[The repository license](../LICENSE) currently permits research use and provides for separate commercial
permission. Record the commercial rights grant and review model, corpus, generated-data, and verifier
redistribution obligations before a commercial pilot. Owning this repository does not settle third-party
rights. This plan changes neither the license nor any customer's deployment authorization.
