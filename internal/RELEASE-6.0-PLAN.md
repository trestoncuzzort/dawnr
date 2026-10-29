# dawnr updates: the working plan (started 2026-10-24)

This file replaces `internal/ROADMAP-LOG.md`, deleted on 2026-10-24 at the user's request as stale. The log's
full text stays in git history (`git show a24d20a2:internal/ROADMAP-LOG.md`). What was still live in it is
carried into section 6. This file is the roadmap of record for ongoing dawnr work; `ROADMAP.md` at the
root is the public face and is updated as milestones finish.

**Working goal, updated 2026-10-29:** ship measured incremental Dawnr releases
and bug fixes, including improved local model weights once they pass the full
qualification protocol. Use Cohere internally to improve checked training
material and use approved cloud compute for training and evaluation. Complete
the current two-seed candidate's evidence audit, selection, one final held-out
reading when eligible, laptop checks and publication before declaring that
model-release work done.

**Research updates this goal's next actions (the user, 2026-10-29).** Whenever a
finding changes the direction, update this working goal with the chosen action,
supporting evidence and measurable success criteria. The current research adds
type/scope-restricted teacher generation and matched example retrieval as the
next bounded experiments after the candidate decision, selected by its measured
failure stage. Read the existing repair training before expanding it. Exact
proposal caps and falsifiers are in
[the next-release research note](RESEARCH-2026-10-29-next-release.md). Those
follow-ups remain conditional on their stated evidence; the current experiment's
frozen inputs and release requirements stay in force.

Runtime research also changes the immediate operating plan: preserve the active
cloud disk across the fixed VM cutoff, recover and verify any required model and
request-cache evidence, then remove the retained disk. The provider requires a
restart to change that runtime limit, so the training run and its 48-hour limit
stay in place. This adds a $5 storage planning allowance and a seven-day cleanup
review; cleanup remains required work.

The user's subsequent speed request adds a current priority: train the already
registered second seed concurrently on a bounded H100 call while the first seed
continues on its L4. Preserve all data, training settings and release conditions,
verify the completed second adapter before adoption, and prevent a duplicate
serial second-seed run. Measure actual throughput before revising the release
ETA. This scheduling amendment precedes any candidate evaluation; it does not
add a third seed or allocate another teacher trial.

The H100 second seed has started after its remote preflight passed. A collector
now waits on that exact call and verifies the completed adapter before importing
it into the original job. The import keeps the original worker checks and
prevents the serial wrapper from training seed 2 again. Its 23 software controls
pass; the real model transfer remains pending on completion.

Observed H100 throughput projects slightly beyond the original eight-hour call
bound. Prepare one continuation of the same seed from its latest complete
checkpoint, only after that exact call reaches its runtime limit and its
container stops. Require at least step 1,900, preserve the original trainer,
data, optimizer, scheduler and random states, and bound the continuation to
90 minutes. This raises the Modal planning allowance from $40 to $50 under
the existing compute authorization. Fourteen software controls pass; no extra
GPU call has been made. The original job and its limit remain unchanged.
[Continuation controls](../release/evidence/parallel-seed2-continuation-2026-10-29.json).

The serial wrapper now has a recorded handoff reservation so completion timing
cannot start duplicate second-seed training. Only that shell is held; its first
training worker has continued advancing with GPU utilization observed at 100%.
Verified parallel-adapter adoption releases the reservation. A failed import
keeps it for inspection. The combined transport, reservation and continuation
controls pass 43 checks; running training sources remain byte-identical.
[Reservation](../release/evidence/parallel-seed2-reservation-2026-10-29.json).

The final-reading tools are installed in a separate immutable cloud directory.
Their exact module, decoder and runtime hashes pass, and an unqualified bundle
is refused before a process can start. The private grading workflow is pinned
to its tested revision. No real seed is selected, no final answer is generated,
and no final grade is dispatched by this preparation.
[Deployment](../release/evidence/private-heldout-tools-deployment-2026-10-29.json).

**Operating clarification, 2026-10-25 UTC:** improve the existing dawnr incrementally as useful changes are found.
Tested application, verifier and data improvements can land independently. A new set of weights is not required
for an update. Section 3 governs changing the released weights and claiming model-quality gains; it does not
hold unrelated code fixes behind completion of a training experiment. Candidate A and B remain experiment labels,
and their old proposed release numbers are not reservations for future product versions.

The first draft of this plan, written the same afternoon, built 6.0 on the corrected 4,189-row set and read
candidates against a control that mixed two training sets. Section 2 records why both were wrong.

## Current pipeline update, 2026-10-29

The objective remains incremental Dawnr releases and bug fixes. The user clarified that Cohere is an internal
resource for improving Dawnr's model, not a backend offered to Dawnr users. Product commands remain local.
Use Cohere to produce and improve checked training material. The user reaffirmed permission for this work and
supplied a current remaining grant balance; that private dashboard figure supersedes historical conservative
estimates for new allocations. Preserve billing records and account for concurrent allocations.

The completed JSON teacher pilot is reconciled against its frozen audit: 500 logical requests, 499 billed
responses, $10.180194 recorded, 3 strictly kept problems and 5 specifications. Coverage, efficiency and
conversion predictions failed, so the unchanged recipe is not expanded. The accepted 6,954-row archive stays
unchanged until another addition passes its checks. See
[the reconciliation](../release/evidence/cohere-json-pilot-reconciled-2026-10-29.json).

The opt-in internal `json-v2` teacher transport uses named operands to enforce fixed operator arities with
Cohere's supported schema features and excludes noncanonical sequence/set type spellings. It restores the exact
original AST and retains every acceptance gate. All 200 valid historical contracts remain unchanged, 479 focused
checks pass, and the one-request cloud capability check passed for $0.014995. This establishes transport
compatibility only. Measure useful new training coverage in a separate registered pilot before expansion.
The transport check itself changed no product runtime, released weights or accepted training data.

The earlier JSON pilot's one still-uncovered problem was subsequently recovered through the full cloud data
build and audit. This adds two rows, taking the accepted archive to 6,956 (6,906 fit, 50 unchanged skips), with
zero audit findings and the same inherited unparsed count. The model candidate and live `json-v2` trial each
retain their frozen 6,954-row inputs. [Data increment](../release/evidence/cohere-json-salvage-2026-10-29.json).

The `json-v2` yield trial has now finished: two strict problems and three specifications
for $11.410546 recorded, with 142/500 accepted conversions. Both problems were already
covered, so it adds no rows. Coverage, novelty, efficiency and conversion targets fail;
the unchanged recipe is not expanded. Of 356 conversion refusals, 347 are static
contract errors. [Trial result](../release/evidence/cohere-json-v2-pilot-result-2026-10-29.json).
The separately registered candidate is training on approved cloud compute, with both
seeds and all release conditions unchanged. Its initial encrypted backup was recovered
and verified against all nine original input files before the first checkpoint.

A bounded [paired static-feedback trial](../t/PREDICT-2026-10-29-cohere-static-feedback.md)
is registered on 35 still-uncovered training problems: one correction using the
previous static diagnostic and one fresh sample per problem. The verifier and
reference gates remain unchanged. Feedback must beat fresh sampling on the paired
strict result, as well as meet the declared coverage and cumulative-cost thresholds,
before expansion. Useful outputs still require a separate full data audit.
The running model retains its frozen inputs. Its first saved checkpoint was also
recovered and checked against all ten independently hashed source files.

The paired static-feedback trial has finished and failed: feedback converted 8/35
replies versus fresh sampling's 10/35, and neither arm produced a strict candidate.
All 70 requests and $1.838487 recorded charges reconciled. It adds no rows and is
not expanded. [Result](../release/evidence/cohere-static-feedback-result-2026-10-29.json).

The independent 6.0.2 patch release shipped on 2026-10-29 with the already validated
Frama-C certificate repair and internal pipeline fixes. Its published-model bytes
are unchanged. Fresh laptop workloads passed with latency and memory ratios below
1.10 and no thermal slowdown. All eight CI jobs and clean Ubuntu/macOS installations
passed before publication. The tag, downloaded manifest and latest-release status
were verified ([receipt](../release/evidence/release-6.0.2-2026-10-29.json)).
This ships useful bug fixes while the separately registered model trains; it does
not complete the ongoing weight qualification objective.

The [grading handoff](../t/PREDICT-2026-10-29-cloud-grading-handoff.md) validates
completed encrypted model outputs before submitting the twelve development parts
and four private measurements to the existing frozen workflows. It retains valid
zero-answer runs, rejects foreign/private public members, and records dispatches
so an observation timeout cannot silently repeat a grade. No held-out reading or
model selection is triggered by this collector.

All six matched released-model control parts have now passed the corrected
zero-task grader and the independent content audit. Clean counts remain
20, 19 and 19; all-seven counts remain 9, 8 and 9. Nine timeout-related cells
changed without changing any counted problem set or emitted source bytes;
each difference is preserved and investigated, with no favorable retries.
Before any candidate grade, the baseline was frozen and both collectors were
reactivated against the same immutable workflow tag after 149 focused checks.
Precision, spec33, training and generation remain unchanged.
[Matched control](../release/evidence/matched-grading-control-2026-10-29.json).

The [current selection checks](../t/PREDICT-2026-10-29-two-seed-selection.md)
recompute the registered six-versus-three statistics and choose only among seeds
passing precision and spec33. They bind the chosen final export and refuse a later
switch. Actual artifact audits and the single private held-out launch remain
separate prerequisites; implementation tests do not qualify a model.

The [artifact content auditor](../t/PREDICT-2026-10-29-grading-artifact-audit.md)
checks original generation bytes, reconstructs extracted tasks, validates complete
kernel tables and recomputes measured totals against frozen source identities.
The existing baseline, precision, spec33 and zero-task controls reproduce through
it. Precision accounting now follows all scored candidates, as the unchanged
instrument requires, while retaining the 0.70 threshold. Artifact-origin checks,
generation/model binding and collector integration remain explicit prerequisites
before using this reader for selection.

A [separate identity observer](../t/PREDICT-2026-10-29-model-generation-identity.md)
is running on the approved cloud host before either spec33 generation starts.
It will bind observed server/client processes, exact model bytes, fixed questions
and complete answers, while preserving the current training and decoding recipe.
Its startup checks passed; the completed identity records still await generation.
Those records must be recovered and audited before a model label can satisfy the
selection evidence requirements.

The [identity content reader](../t/recipes/release_model_identity.py) now checks
the recovered training/export records and the observed spec33 invocation. The
selection guard requires its spec33 weight digest to equal the final export,
development and precision digests, and binds the identity receipt itself. The
result collector recovers the four identity groups and produces a deterministic
per-seed generation audit only after all eight measurements agree. Its completed
state requires both seeds' bindings; it does not make a release decision itself.

The operator assembler now joins those complete audits into the registered
three-versus-six decision and can freeze an eligible choice. Its same-results
control correctly fails the improvement condition, and twelve focused checks
pass. The actual-input probe writes no choice while the matched baseline
registration and both trained seeds remain pending.

The [private final-reading handoff](../t/PREDICT-2026-10-29-private-heldout-handoff.md)
now recomputes the qualified seed choice, binds one immutable generation claim,
and prepares encrypted inputs for a separate frozen cloud grader. Its synthetic
transport checks preserve complete zero-answer readings and reject changed or
incomplete evidence. The workflow is prepared, not dispatched. Complete the
matched grader controls, audited evidence assembly and selected-model launch
binding before using it; its final result still needs the content audit and
laptop checks. The 182-problem panel, 17-call limit and 17/12 score floors remain.

The prepared final-reading launcher adds the actual model and child-process
binding to that handoff, and the sealed grader requires its invocation receipt.
Its 59 combined software checks include harmless process/listener stand-ins and
same-cache recovery. No real final reading has been launched; actual model
qualification, deployment and final evidence remain pending.

The provider confirms the current VM will be deleted on October 31 at 16:28 UTC.
Its boot disk is now preserved so the cutoff cannot also erase unuploaded caches.
The VM's last start, cutoff, training/observer process IDs and all four worker
hashes remained unchanged; training advanced to step 695 during the checks.
The existing cloud planning allowance is now $55, including $5 for temporary
disk retention; no additional GPU runtime was allocated. Independently recover
needed evidence, then restore auto-delete or remove the detached disk. The
cleanup review is due November 7 at 16:28 UTC; disk deletion is not automatic.
[Verified change](../release/evidence/candidate-runtime-retention-2026-10-29.json),
[provider runtime rules](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime),
[disk retention](https://docs.cloud.google.com/compute/docs/disks/modify-persistent-disk).

The frozen development grader rejected complete zero-task outputs. The
[zero-task repair](../t/PREDICT-2026-10-29-empty-grading.md) records those as zero
coverage through the existing scorer, retaining the original nonempty proof and
reference commands. One cloud software control and a matched regrade of the six
saved baseline parts are registered before candidate use. The running collector
keeps its prior frozen workflow until those controls validate an amendment.

Research for the following release cycle is in
[the October 29 next-step note](RESEARCH-2026-10-29-next-release.md). It prioritizes
type/scope restrictions and matched example retrieval inside the Cohere teacher,
then a reading of the existing repair training. Its proposed trials and spending
caps do not change the current candidate or allocate a new run. A read-only
training census located all 339 inherited unparsed blocks in prompts, with none
in chosen targets; this resolves their location, not their behavioral audit gap.

## 1. What 6.0 is

dawnr has shipped through one rolling channel whose model is dawnr v5. Since v5, five candidate lines were trained
or prepared and each was called a version: v6, v7, v8, v9 and v10. None was promoted. 6.0 folds all five into
versioned releases (the user, 2026-10-24: "drop the student and vN niche and just call it dawnr X.Y.Z"): 6.0.0 ships
now with the October 5 model unchanged. Subsequent updates carry tested improvements to the existing system.
Replacing its weights additionally requires the checks in section 3. The version names the whole system:

- the application at a tested revision, with `dawnr version` printing it;
- dawnr running smoothly on a laptop like the one it is built on (an RTX 5050 Laptop GPU with 8 GB, 16 cores,
  15 GB of memory), measured there as a release condition;
- the qualification protocol as code and as a document, so a model enters the release only one way;
- the instruments the five lines produced: the ceiling instrument and its gate precision, the three-decode report,
  the strict reference check (1,000-draw request budget, at least 10 valid draws, both mutant families at 90%),
  the annotation held-out set;
- the data every useful line contributed, on v5's own base, trained on two seeds and read by the protocol;
- the model that passes that reading, or v5's weights under the 6.0 card if none does, said plainly;
- the receipts under `release/evidence/` for every number in the card.

The names v6 to v10 stay in the PREDICT records as the names of measured artifacts. Nothing is renamed in history.

## 2. What the records showed on 2026-10-24

**Every candidate since v5 trained on a different base than v5.** The published v5 trained on 5,095 rows (SHA-256
`848fca29…`, its model card; recovered 2026-10-11, `t/out/v5-rebuild-20261011/desktop-source-recovered.json`).
Every later candidate trained on a corrected set: `e14f766f…` (4,189 rows: the 3,352 of v5's rows that passed the
2026-10-11 audits, 1,315 uDebug rows of which 909 are judged by Python tests with no proof, and 406 recovered
student rows, deduplicated) or its corrective snapshot `8aa1b752…` (4,089 rows).

**The training-seed arm changed the rows too.** The model registered as "v5's exact rows with seed 2" trained on
`e14f766f…` (`t/out/v5s2-20261022/manifest.json`, `data_sha256`). Its readings compare a different training set on a
different seed against v5, so "a training seed alone moves the count by two" is not supported by it, and a control
built from v5 plus that model mixes two training sets.

**The 240-problem panel holds 34 problems v5's rows had matched.** It is the 95 development problems plus all 145 of
the wider reader's pool; `heldout_audit.wider_flagged()` marks 34 of the 145 as matched by the rows of 2026-10-05.
The clean development panel is the 95 plus `heldout_audit.wider_clean()`, 206 problems.

| reading | v5 (original rows, seed 1) | corrected set, seed 2 | paired, per problem |
|---|---:|---:|---|
| clean, mean of three decodes, 206 unleaked | 19.33 | 14.67 | v5 better on 12, worse on 8; sign p 0.50, permutation p 0.15 |
| all seven, the same | 8.67 | 6.33 | better on 4, worse on 2; permutation p 0.25 |
| clean, the 34 leaked | 10.67 | 8.33 | better on 6, worse on 4; permutation p 0.43 |

First decodes on the 95: v5 6 (three decodes 6, 4, 6), v6 on the corrected set 4, the seed-2 model 4 (4, 5, 4),
v9 (the corrected set plus 833 strict self-distilled rows) 7 on its one decode.

**Reading.** Every model on the corrected set sits at or below v5, and v5 leads it on the unleaked problems on
average, but no paired test separates them. A weaker base is likely and not proven. 6.0 does not need the answer:
it builds on v5's own rows and reads the result against the published v5 alone, on unleaked problems.

## 3. Checks for replacing the released weights

Registered here and repeated with numbers in the candidate's PREDICT file before training. All five must hold:

1. **Paired reading on the 206.** The candidate's six decodes (two seeds, three decodes each) against the published
   v5's three, per problem, on the clean development panel (`t/out/release-6.0/dev-206.txt`, written in M1 from the
   95 and `wider_clean()`), with `t/recipes/three_decode_report.py`. More problems up than down, permutation p at
   or below 0.05. Declare `--expected-baseline-decodes 3 --expected-candidate-decodes 6` when reading a release
   candidate. The report validates the original 95- and 145-problem grading receipts before restricting their
   solved sets to the 206; a missing declared decode is refused.
2. **Gate precision.** On the ceiling instrument, the three-test gate's precision is at least 0.70 (v5 0.785).
3. **Given specifications.** At least 27 of the 33 held-out specifications proved by all seven kernels at Q8_0.
4. **Held-out 182, read once.** After 1 to 3 decide, the winner is read once on the clean 182 under the
   larger-inputs instrument (`t/score_levels.py --larger`) and must not fall below v5's 17 at one or more kernels
   and 12 at all seven. The held-out number never selects between candidates.
5. **Smooth on this laptop.** From a clean checkout on the laptop: `./install.sh`, `dawnr doctor`, and the README's
   example commands complete; the median command time and the peak memory are within 10% of v5's on the same
   machine; no software thermal slowdown is reported on the GPU during the run. v5's baseline is measured first
   (M1).

A mean is never a verdict. A weight experiment that does not pass leaves the installed weights in place;
the record says what was measured. Tested application, verifier and data updates continue independently.

The repaired evaluator's fixed-answer spec33 control completed as 27 all-seven / 29 at one or more kernels.
The exact prediction of 28 / 29 failed: the certificate refusal is repaired, while the existing Frama-C
timeout remains. All other 230 cells are unchanged from the earlier cloud control. The standing threshold
of 27 remains unchanged. Receipt: `release/evidence/spec33-certificate-control-2026-10-25.json`.

## 4. Ongoing weight experiments: candidates A and B

**Base.** v5's 5,095 rows minus what today's policy refuses: the GPL lineage (`--refuse-gpl`; 61 rows built from
MBPP-DFY programs) and any row touching a panel in use (the held-out 182, the development 95, the wider clean 111,
the 33 specifications). Rows that match problems already out of the panels are kept, the standing policy recorded
in the v9 registration. The 2026-10-11 audit kept 3,352 of the 5,095 under the stricter rule of that day. Re-run 2026-10-24 under
today's policy: 62 rows refused (61 GPL lineage, 1 held-out problem 629 as a twin) and 9 more views of the refused
problems, 5,024 rows kept (`014e5a32…`, `out/release-6.0/base-families.json`). The uDebug rows stay out (they are one of the suspects; an ablation can test
them later).

**Added, each rebuilt against this base with `t/recipes/v8_spec_rows.py` (problems the base already covers are
skipped) and audited with `t/heldout_audit.py --panels --refuse-gpl`:**

- v9's strict self-distilled specifications: 985 candidates over 536 problems that passed the strict check.
- The teachers' strict-kept specifications: DeepSeek v3.2 on Bedrock and the primed 9B, 468 over 255 problems
  (`out/v10/teacher-strict-kept.jsonl`), plus the four remaining 9B chunks (`teacher9b-20261022c-tc06` through
  `tc09`) once `t/recipes/v9_strict_specs.py` has checked them. The saved strict report already lists the chunks
  through `tc05`; its timestamp is 2026-10-22 21:17Z. The earlier 16:17Z cutoff in this plan was stale.
- The repair traces: 232 from the student's own dropped candidates and 293 from the teachers'.
- **The Cohere teacher (new, written permission 2026-10-24).** `command-a-reasoning-08-2025` and
  `command-a-plus-05-2026` piloted head to head on the same 50 failed training problems with the DeepSeek lane's
  prompt. Checked coverage, novel problems, quota and documented API cost decide the recipe; subsequent passes
  target remaining failed problems in size order. Every call is recorded in the grant ledger
  (`~/.config/cohere/ledger.jsonl`, planning stop at $950).
  Every Cohere-written row is labelled by source and the data card cites the permission
  (`internal/COHERE-GRANT-UPDATES.md`). Cost basis for the pilot: the DeepSeek lane used about 37,000 prompt and
  3,200 reply tokens per problem; at Command A's listed $2.50 and $10 per million that is about $0.13 a problem
  before reasoning tokens, so roughly $15 to $30 for the pilot. The ledger records the real figure.

**Which candidate has what.** Candidate A (registered and training since 2026-10-24,
`t/PREDICT-2026-10-24-release-6.1-candidate-a.md`, 6,727 rows) has the base, v9's and the earlier teachers'
strictly kept specifications and the repair traces. Candidate B adds the Cohere teacher's rows and the four
remaining 9B chunks, once the strict check has passed them. Their data hashes and training receipts identify
the weight experiments; routine dawnr updates continue as their own checks finish.

**Recipe.** v5's, unchanged: Qwen/Qwen3.5-4B at 851bf6e8, QLoRA NF4, rank 64, alpha 16, dropout 0.1, lr 2e-4,
5 epochs, max-len 2845, batch 1, grad-accum 16, `t/student_sft.py` at its pinned digest, seeds 1 and 2.

The encoder skips oversized rows and counts them, without truncation. Candidate A's existing training log
reports 6,678 used and 49 skipped from its 6,727-row archive. An offline check of the complete updated
7,176-row archive reproduces those inherited skips and adds three, yielding 7,124 fitting rows. The 449
additions since candidate A contribute 446 fitting rows. These counts describe the unchanged recipe;
no new training is started. Receipt: `release/evidence/cohere-data-window-2026-10-25.json`.

## 5. Where work runs (the user, 2026-10-24: "outsource for this stuff always. we use the laptop to test if something doesnt work")

- **The laptop is for tests:** a quick check when something does not work, and the release's own laptop condition
  (does dawnr run smoothly on this laptop). Decoding candidates, seven-kernel grading, the ceiling and spec-33
  readings, strict checks, teacher lanes and full test suites run elsewhere.
- **GitHub runs the CPU work:** test suites on every code push (read `gh run list`), installation checks on fresh
  Ubuntu and macOS machines, teacher orchestration, strict specification checks, training-row builds and audits,
  and seven-kernel grading. Private inputs and Cohere outputs are encrypted in transit through release assets
  and workflow artifacts.
- **Cohere's API writes the training material.** The full pass and subsequent pilots run from GitHub via
  `.github/workflows/teacher.yml`; checked outputs feed candidate B under the recorded written permission.
- **The existing candidate A training may finish on the desktop.** This is the sole exception to the user's
  later instruction that both local machines are for final testing. No new local training, model decoding or
  full grading is authorized by this plan.
- **New training and GPU evaluation run on approved cloud compute.** Google Cloud authentication and unused L4
  quota were verified on 2026-10-24. A bounded evaluation instance is prepared, but the separate compute-spend
  question remains unanswered. Launch only after that answer and both candidate A seed adapters are complete;
  keep the instance unprovisioned while waiting. Cohere's grant allocation does not establish a Google Cloud
  credit balance.
- **Remote development decoding:** `release_arms.sh PFX GGUF IDENT` requires explicit `D` and `L` for the approved
  GPU host. It runs only the six registered development parts, with the same settings and seed offsets. Each
  completed part gets an atomic archive and receipt under `t/out/release-decoded/PFX`; `arms.json` lists the parts
  ready for `evaluate.yml`. Fetch and verify these checkpoints as they finish. The driver refuses decoder
  failures, changed model/procedure reuse, foreign panel rows and unreceipted older output. It performs no grading.
  The old local `release_candidate.sh` exits before work; export directly with `v6_export.py` on the GPU host.
  The oracle instrument and `spec33.sh ... ask` remain separate registered steps; their evidence is handled
  according to its existing privacy rules. An eight-hour VM limit is not a promise that all work fits that window.
- **Specification-gate precision:** `.github/workflows/ceiling.yml` takes encrypted saved stage-1 answers for the
  development 95 and runs the unchanged `spec_ceiling.py` at grader revision `01c94ef5`, with 200 reference draws.
  The original v5 inputs are replayed first under `t/PREDICT-2026-10-25-ceiling-cloud-control.md`; the expected
  control is 73 reference-correct among 93 kept. This measurement asks no model and runs no proof kernels.
  Control `40149932546` reproduced every field of the original result, with all 558 source hashes verified;
  aggregate receipt `release/evidence/v5-cloud-ceiling-control-2026-10-25.json`. For a candidate, generate the
  original stage-1 instrument on the approved GPU host with ten Python attempts, twenty specification candidates
  and `--specs-only`, seeded from its own offset-zero development cache. Transfer the three saved input files and
  panel privately to this workflow; no additional proof generation is needed to measure gate precision.
- **Large files without the cable** go through a private GitHub repository used only for transfers. With the cable
  plugged in, Tailscale uses it directly.

### The Cohere lane, measured (2026-10-24)

The same 50 failed training problems, ten candidates each, kept by the route and then by the strict check:

| model | problems kept by the strict check | candidates kept | historical ledger estimate | replies cut off |
|---|---:|---:|---:|---:|
| Command A Reasoning (thinking 2,048) | 9 | 18 | $33.83 | 113 of 500 |
| Command A+ (thinking 2,048) | 6 | 11 | $31.96 | 24 of 500 |
| Command A (no thinking, 2,048-token replies) | 4 | 9 | $6.48 | 9 of 500 |

Command A Reasoning and Command A+ are limited to 20 requests a minute and 1,000 calls a month even on a production
key (docs.cohere.com/docs/rate-limits), so the full run (about 17,000 calls) uses Command A (500 requests a minute,
no monthly cap). Current model pages list API evaluation of Reasoning and A+ as free within those limits; their
positive ledger entries above came from conservative placeholder rates, not verified invoices. The earlier
per-dollar advantage claimed for Command A is withdrawn in `CORRECTIONS.md`. Its own pilot produced about 62
strictly kept problems per $100 at its configured API rate, the absolute bar registered for the wider Command A
pilot. The remaining 1,705 problems were processed on GitHub (`.github/workflows/teacher.yml`, ten lists in parallel), with
further work chosen from actual yield, quota and reconciled budgets.

The full pass started on GitHub at 22:28Z on 2026-10-24, run `40138722401`: 1,705 distinct training problems in
ten jobs, Command A, ten candidates per problem, 2,048-token replies, $60 per-job ceilings ($600 allocated, not
spent). The prior desktop ledger was $77.9143 and the GitHub smoke cost $5.167696. Outputs are encrypted before
upload. After the jobs finish, `t/recipes/teacher_outputs.sh` opens them and `t/recipes/cohere_run_report.py`
reconciles the strict-check counts and all supplied ledgers, writes the private kept rows, and lists problems
still without a strictly kept specification. The next pass uses a fresh series and sampling seed offset; its
budget comes from actual remaining credit, with the $950 grant stop retained. The report's remaining allocation
assumes no other live grant run, so outstanding job allocations must also be reserved before dispatch.

Two follow-up pilots completed on 2026-10-25. The wider Command A recipe (20 candidates, 4096-token replies)
kept 5 problems and 9 candidates for $13.064852, below both registered expansion targets. All five were already
covered. North Mini Code with default thinking kept 4 problems and 7 candidates, also all covered; 481 of its
500 replies hit the token limit and 480 contained no final text. Neither recipe qualifies for expansion, and
neither adds rows to the current draft. Aggregate receipts are in `release/evidence/cohere-wider-pilot-2026-10-25.json`
and `release/evidence/cohere-north-pilot-2026-10-25.json`.

A registered one-request North configuration smoke with 2048 thinking tokens plus 4096 answer tokens returned
a complete nonempty answer. It kept no strict example and establishes no quality result. Its successful
configuration check permitted the registered 50-problem follow-up, `40149580546`. It completed with 10 strict-kept
problems and 16 candidates, but only one new problem. Two expansion conditions failed: novelty was below four
and token-limit finishes were 6%, above the 5% ceiling. Fifteen requests hit the model's monthly quota; every
successful call returned nonempty final text. The one new specification remains eligible for an audited data
increment. The recipe is not expanded, and further North calls wait for its quota to change. Receipt:
`release/evidence/cohere-thinking-pilot-2026-10-25.json`.

The full Command A pass completed all ten jobs. It accounted for all 1,705 training problems and kept 250
specifications on 149 problems, with 16,846 successful calls, 194 HTTP 422 errors and ten HTTP 400 errors.
The recorded cost was $214.499216. All ten encrypted artifact digests and all 280 archived files were verified
against the collected evidence. Aggregate receipt: `release/evidence/cohere-full-pass-2026-10-25.json`.

At completion of those teacher runs, their allocations were released. The historical subtotal was
$310.646105, leaving $639.353895 below the $950 planning stop. This counts the common prior $83.082037 once,
the wider pilot's $13.064852 once, and the full pass once; all three North runs recorded zero API cost.
Historical placeholder prices remain estimates, not verified invoices. The separately registered schema
capability test completed for $0.002285, releasing its $1 reservation. Including that test, the conservative
total was $310.648390. The subsequent full JSON transport check passed for $0.018010, bringing completed
conservative accounting to **$310.666400**. The registered 50-problem JSON pilot `40160251665` is now running
with a $25 proxy ceiling and $32 reserved for in-flight requests. Completed cost plus that reservation is
$342.666400, leaving $607.333600 unreserved below the $950 stop. The proxy ceiling is not a hard billing cap.
Its original codec, expected requests, novelty baseline and expansion conditions remain fixed while later
pipeline corrections land. See `t/PREDICT-2026-10-25-cohere-json-pilot.md`.

The audited draft already incorporates eight Command A shards. The final two shards and the bounded North
pilot supply 39 additional uncovered problems and 71 specifications. Their next encrypted data build is
registered in `t/PREDICT-2026-10-25-cohere-data-completion.md`, expecting 110 added rows and 7,176 total.
Build `40155901277` met that count and passed the full audit with no new findings or unparsed blocks. Its
length prediction failed: three specifications exceed 2,845 tokens, so the existing trainer skips them.
The other 107 additions fit, supplying 39 reference-Python rows and 68 specifications on 38 new specification
problems, plus one reference-only problem. The full 7,176-row audited archive is retained; it is not a claim
that every row fits a training run. Exclusions and hashes: `release/evidence/cohere-data-2026-10-25b.json`.

The subsequent static compatibility check found a separate data-boundary gap: 50 of the full pass's 250
reference-kept specifications fail the engine's static rules, after allowing the existing checked header
promotion. Reference agreement alone had not excluded undeclared calls, circular postconditions or type
errors. The original reference-only counts remain recorded; 200 specifications on 125 problems pass the
static check. Future strict checks now apply that gate before reference evaluation, and row preparation
independently checks it. The correction is recorded at the top of `CORRECTIONS.md`.

A remote curation build is registered in `t/PREDICT-2026-10-25-static-contract-data.md`: preserve the original
6,727-row candidate A prefix, remove 50 invalid additions, apply the existing header promotion where it alone
clears all errors, and remove three normalization duplicates. Expected archive: 7,123 rows, with 7,072 fitting
the unchanged training window. The full panel/GPL audit had to pass before the JSON teacher pilot proceeded;
that condition was met while the baseline experiment kept its frozen inputs.
Build `40157909167` passed all three registered predictions. That curated archive has 7,123 rows,
SHA-256 `eb139437b33b4797023e1f6ef121628588d5397f9f57241695d654071c4457b5`, with 7,072 fitting the unchanged
window. Its 396 additions contain 166 reference-Python rows and 230 statically valid specifications; 22
retained headers were promoted under the existing rule. The baseline prefix, zero panel/GPL findings and
339 inherited unparsed blocks are unchanged. Receipt: `release/evidence/static-contract-data-2026-10-25.json`.

The inherited specification census then exposed a pipeline context error: declarations with task termination
measures were checked as though their bodies were complete. The factorial fixture reproduces it. The corrected
pipeline preserves those measures and still checks their types/scopes and every specification-function body;
the complete-program checker and proof gates are unchanged. This recovers 47 inherited declarations, leaving
124 specification targets that still fail. The full Command A census and all 230 added controls are unchanged.

The latest data archive comes from build `40162353906`, registered in
`t/PREDICT-2026-10-25-inherited-spec-curation.md`. Its explicit `all_source_spec` scope checks inherited and added
specification targets while preserving every other row and its relative order. All predictions held: **6,954 rows**,
SHA-256 `18f3b204abd15c8e497c83840f909877ce5d131a8c23ce6c8633a117e5dbb4f9`; 5,292 unchanged other rows and
1,662 checked specification targets. It removes 124 invalid targets, 42 existing duplicates and three duplicates
created by normalization, and retains 69 checked header promotions. The whole-data audit has zero findings and
the same 339 inherited unparsed blocks. The unchanged tokenizer/window admits 6,904 rows and skips 50 inherited
overlength rows, with no new skip or truncation. All artifact, source, row-action and audit evidence is verified
in `release/evidence/inherited-spec-curation-2026-10-25.json`. This is the current archive for further preparation;
the active candidate A training and the registered JSON pilot's novelty comparison retain their original inputs.

The syntax-loss evidence motivates a different representation as a research hypothesis. Command A supports
[JSON Schema output](https://docs.cohere.com/docs/structured-outputs), and `t/SPEC.md` already defines the engine's
JSON task representation. Schema mode supports references and `anyOf`; plain JSON mode is limited to five nesting
levels, and several schema features such as `oneOf` and array-length bounds are unsupported. A small remote
capability check must establish the needed schema behavior before a teacher pilot. Engine structure, type and
reference checks must still validate every result; valid JSON alone is not an accepted specification. A fixed
three-request capability test was registered in `t/PREDICT-2026-10-25-cohere-schema-smoke.md`, with an initial $1 reservation.
It separates inline, referenced and recursive schemas on synthetic contracts, before any teacher pilot.
Run `40156495978` passed all three cases, including the depth-eight recursive expression. Each result was
well formed and survived an exact printer/parser round trip. Receipt:
`release/evidence/cohere-schema-smoke-2026-10-25.json`. This permits preparing a registered training-only
pilot with the full needed representation and unchanged semantic checks; it establishes no teacher-quality gain.
A complete JSON contract transport is now implemented as an opt-in teacher representation, retaining the
original six examples and all problem/test/Python evidence. Its full schema validates the 200 statically
eligible historical contracts. The next registered check is one synthetic request through the actual
decoder and converters (`t/PREDICT-2026-10-25-cohere-json-transport.md`), with a separate $1 reservation.
Its live planning amount is $311.648390. A real training-only pilot waits for that complete transport check.
The complete transport check passed as `40159613022` for $0.018010, with all inputs, wire evidence and code
hashes verified. Its reservation is released; the conservative total is $310.666400. A real JSON teacher pilot
on the unchanged original 50 IDs is registered in `t/PREDICT-2026-10-25-cohere-json-pilot.md`: ten candidates,
8,000-token replies, a $25 proxy ceiling and $32 reservation including in-flight requests. Combined planning
is $342.666400. Expansion requires new usable coverage, strict yield, efficiency and complete accounting;
the diagnostic conversion-rate prediction is reported separately. No training or weight change is implied.
This follows the existing grammar-generation research in
`internal/research-2026-10-22/plateau-repos-B.md` and the measured pilot attrition, rather than assuming another
prose instruction or repair prompt resolves the earlier failures.

The grant's purpose is to train dawnr with these checked outputs, as the written permission allows. Candidate B's
row build uses `t/recipes/v8_spec_rows.py --tag cohere:MODEL:SERIES` to preserve that provenance; the default
self-distilled label applies only to self-generated rows. The audit and release conditions still decide what is
eligible and whether the resulting model improves on the released one.

`.github/workflows/prepare-rows.yml` builds and audits those private rows on GitHub. Its input archive is encrypted
with the separate repository input key and pinned by SHA-256; its rows and diagnostic logs leave encrypted to the
same local output key as the teacher runs. `t/recipes/prepare_release_rows.py` checks every source's digest and
strict-check evidence, applies the sources in the manifest's stated order with explicit provenance tags, then
requires the full `heldout_audit.py --panels --refuse-gpl` to pass before writing a completed dataset receipt.
The first integration build uses candidate A's 6,727-row base and the three completed Cohere pilots, whose kept
outputs cover 12 distinct problems. Prediction: at least one added row and zero current-panel or GPL-lineage
findings. Zero added rows or any such finding falsifies the corresponding prediction. This build tests the
data path; candidate B's final data hash is registered after the full teacher pass and before training.

The integration build passed on GitHub, run `40140570064`: 35 added rows over 12 problems (12 Python rows and 23
specification rows), 6,762 total, SHA-256 `818f164a…`; both predictions held. The base's 6,727 rows are unchanged.
The whole-dataset audit reports zero current-panel or GPL-lineage findings and the same 339 unparsed program
blocks as the base, with none added by the Cohere rows. Those inherited blocks remain a limit of the behavioral
audit, not evidence of a successful check. Counts and hashes, without training text:
`release/evidence/cohere-pilot-rows-2026-10-24.json`. This is data preparation; no new model has trained from it.

The given-specification condition can now be measured off the person's machines too: `spec33.sh LABEL GGUF ask`
generates answers on a GPU host selected by `D` and `L`; `.github/workflows/spec33.yml` grades the encrypted,
complete answer set in the existing pinned kernel image. It refuses a changed 33-question panel, missing or
duplicate answers, mixed model/prompt metadata, or an incomplete kernel table. Its control is registered in
`t/PREDICT-2026-10-24-spec33-cloud.md`: replay the saved October 11 v5 answers and predict their previous 28
all-seven count. That control does not change the release requirement of 27 and does not read the held-out 182.

The control completed in run `40141581001`: 29 at least one reproduced, but 26 all-seven falsified the prediction
of 28. Two of 231 cells changed, both Frama-C, on identical saved tasks and generated C. A new adapter guard
rejects a negated inequality after the kernel printer rewrites it as equality; a second cell timed out.
`t/PREDICT-2026-10-24-spec33-cloud.md` records the failed prediction and a bounded private diagnostic. No release
threshold or engine rule has been changed to recover the count.

The two-pair diagnostic completed in `40145445753`: the negation-guard reason repeated in all three affected
twin calls. The prior timeout did not repeat; that real/twin pair read verified/refuted three times at the same
budgets. The second diagnostic prediction therefore failed and the timeout's cause remains unestablished.
These targeted results do not replace the original full-control score of 26.

The development baseline completed in run `40134628181`: clean-206 counts 20, 19, 19 (mean 19.33), and all-seven
counts 9, 8, 9 (mean 8.67), reproducing the recorded baseline. All six original 95/145-problem receipts were
validated before filtering, and their evaluator hashes agree apart from the panel paths. Aggregate receipt:
`release/evidence/v5-cloud-baseline-2026-10-25.json`. The image pins prover binaries; it does not freeze the
mounted checkout. Those measurements used grader revisions `01c94ef5` and `878a5cb3`, respectively. The validated
certificate-normalization repair is now imported at `66be29b4`, and both workflows explicitly pin that revision.
The same saved answers were regraded under `t/PREDICT-2026-10-25-framac-control-refresh.md`; the original
receipts remain recorded. The completed matched development control is in
`release/evidence/v5-certificate-control-2026-10-25.json`: all six full-panel receipts and source/input hashes
verified before joining the 206; clean counts 20, 19, 19 and all-seven 9, 8, 9, with identical per-problem
acceptance sets. Seven of 1,274 matrix cells have different timeout-related outcomes in SPARK or F*, on
identical emitted sources, without changing a score. Every changed cell is recorded and no favorable rerun
replaces it. The verifier fix is an incremental code update. Its refreshed measurements establish
the evaluator for later weight comparisons, and are not themselves a claim that the weights improved.

The remaining 9B inputs contain 30 candidates on 18 problems, 15 not already covered by candidate A. Their
concatenated SHA-256 is `81d04eaaf849f85f7e279fb7455fbeb62fca75f07523047560e3353014b03355`;
all four request-cache identities name the same Qwen3.5-9B Q4_K_M model (`8c4cc24f…`) and pinned llama.cpp server.
`prepare-rows.yml` can now accept a pinned `raw_kept` source: it refuses non-training IDs, runs the existing
1,000-draw/0.9 strict check, validates that evidence, then builds rows and audits the whole dataset. The next
data build starts from the 6,762-row Cohere-pilot integration dataset. Prediction before dispatch: at least one
additional row and zero current-panel/GPL-lineage findings. A zero or any finding falsifies the respective
prediction. No teacher is restarted and no new model call is made for this check.

That check passed in run `40142218970`: 25 candidates on 14 problems survived; three problems were already
covered, so the build added 33 rows on 11 new problems (11 Python rows and 22 specifications). The resulting
6,795-row draft has SHA-256 `4ba7ce5c…`, zero current-panel/GPL findings, and the same 339 unparsed base blocks.
All 33 additions fit the registered 2,845-token limit (210 to 834 tokens). Both data-build predictions held.
Receipt: `release/evidence/late9b-rows-2026-10-24.json`. The full Cohere pass is still needed before candidate B's
final dataset is registered and trained.

The saved GitHub smoke run (`40134918870`) also has four strictly checked candidates on four problems absent
from that 6,795-row draft. Preserve these accepted outputs even if the ongoing full pass does not reproduce
them. Its kept-file SHA-256 is `d4f8330c436d10ff6b596a976233c630f2662c47fafdda93aa6937e02305734e`;
the original strict report records 1,000 draws and the 0.9 floor. Prediction before the encrypted integration
build: eight added rows on four problems and zero current-panel/GPL-lineage findings. A different added-row
count or any such finding falsifies the respective prediction. This reuses saved outputs, incurs no new API
spend, and remains a data draft until all completed teacher sources are reconciled and candidate B is registered.
Before another teacher pass, remove problems already covered by this draft as well as all subsequent strictly
kept sources; a single run's remaining list does not account for the other teachers.

That integration passed in run `40144638795`: eight rows on four new problems (four Python, four specification),
6,803 rows total, SHA-256 `04ae5b85…`. All previous rows are preserved; the full audit has zero current-panel/GPL
findings and the same 339 inherited unparsed blocks. All eight additions fit the unchanged 2,845-token limit
(477 to 1,144 tokens). Both predictions held. Receipt: `release/evidence/cohere-smoke-rows-2026-10-24.json`.
The saved Cohere pilots and smoke now contribute 43 new rows over 16 problems; the late 9B chunks contribute
33 rows over 11 further problems. These are data gains; model-level qualification remains outstanding.

The next data increment completed in run `40153448857`: the first eight verified full-pass shards added 263
rows on 100 new problems (100 reference-Python rows and 163 specifications). The resulting draft has 7,066 rows,
SHA-256 `633ededffc2be4718c3341393845272268fdbe316d10e7e2fa4549f74ce606dc`; all parent rows are preserved.
The whole-dataset audit has zero current-panel/GPL findings and the same 339 inherited unparsed blocks. Every
addition fits the registered tokenizer and 2,845-token limit (138 to 2,102 tokens). All three build predictions
held. Receipt: `release/evidence/cohere-data-2026-10-25a.json`. Later teacher shards can form another audited
increment; this update changes the data draft without starting training or changing installed weights.

## 5b. Releases so far and the next increments

- **6.0.0, published 2026-10-24 21:15Z** (tag `v6.0.0` at `b03f6ce5`): the October 5 model under version names, versioned
  installs, the `dawnr do` context fix the laptop check found, the correction of section 2. Laptop check with all seven
  provers: every README command works; `ask` 129 s cold is the slow one (`release/evidence/laptop-6.0.0-2026-10-24.json`).
  GitHub's install-smoke run 40133457459 installs it on fresh Ubuntu and macOS.
- **6.0.1, published 2026-10-24 21:50Z** (tag `v6.0.1` at `672ffad9`; its manifest lists 6.0.0's model files by URL, so
  nothing was uploaded twice): `dawnr ask` from a cold start 128.9 s to 64.6 s on the laptop (the provers take the
  answers one at a time and stop at one all seven prove; a profile had shown 92 of 121 s in the provers), peak memory
  8.9 to 6.8 GB, and the launcher adds the person's tool folders to PATH so all seven provers run however dawnr is
  started (`release/evidence/laptop-6.0.1-2026-10-24.json`).
- **Off the person's machines (the user, 2026-10-24: "i only want to use the desktop and laptop for final testing"):**
  `.github/workflows/evaluate.yml` grades decoded arms with the seven kernels on GitHub's machines (its image of
  t-proof-engine's pinned Dockerfile built in 18 minutes and stays in the Actions cache, never published);
  `.github/workflows/teacher.yml` runs the Cohere teacher and the strict check there. Inputs are assets of the
  pre-release `eval-inputs`. Cohere's grant is authorized for the checked training-material work. The existing
  training run may finish, and later GPU work follows the compute arrangement recorded in section 5.
- **Weight experiment A:** the registered training run and its measurements.
- **Weight experiment B:** the existing base plus audited additions, including Cohere's strictly kept
  specifications. Software and data updates continue as their own checks pass; product versions are not reserved
  for these experiments.

## 6. Where things stand (carried from the deleted log, paused by the user 2026-10-23 04:52Z)

Nothing below restarts until the user says so.

- **Desktop:** `dawnr-v9s2-train.service` stopped at step 1008 of 1535 (checkpoints 900 and 1000 kept) and was
  disabled with the finished v5s2, v8 and v9 units. It is not resumed: its comparison was built on the mixed control.
  The out/ backup of 2026-10-23 is at `~/dawnr-out-backup-2026-10-23/` there.
- **Laptop:** the v9 arms driver, two native wider grades (`v9-20261022-wider-off1000` and `-off2000`; no resume,
  about seventy minutes each), the 9B teacher lane (131 kept specifications; the final four chunks not yet
  strict-checked) and the tandem waiter were stopped.
- **v9's arms in hand:** dev (7 clean, 2 all-seven on one decode), seedoff1000, seedoff2000, wider-off0. Ceiling
  read 2026-10-23: gate precision 0.682; a reference-correct specification within five candidates on 25 problems
  (v5 18), within twenty on 31 (v5 29). Receipts `release/evidence/v9-ceiling-2026-10-23.json`,
  `v9-oracle39-2026-10-23.json`.
- **Teachers so far:** DeepSeek v3.2 kept 193 of 906 failed training problems (21%; 9,090 calls, 33.5 M tokens in,
  2.9 M out); the 9B keeps 16 to 20 of 50 short problems and 2 to 3 of 100 long ones. About 1,800 failed problems
  remain, the long tail, which the Cohere lane is for.

## 7. Milestones, each with its DONE WHEN and its Cohere update

The original milestone locations below are superseded by section 5's execution policy: existing candidate A
training may finish, subsequent compute is outsourced, and local machines perform final testing.

| | milestone | DONE WHEN | where |
|---|---|---|---|
| M0 | this plan, the scaffold (`VERSION`, `dawnr version`, the log retired), the public correction of section 2, and the dawnr 6.0.0 release (the October 5 model under version names, versioned installs) | CI green on the commit; the release installs from a clean checkout | laptop |
| M1 | v5's laptop baseline for condition 5; `dev-206.txt` written; optionally v9's two unfinished wider grades | baseline numbers and the panel file on main | laptop |
| M2 | base audit under today's policy; the Cohere pilot and lane; rows built, audited, hashed; the PREDICT file with the five conditions | `t/PREDICT-2026-10-2x-release-6.0.md` on main before any training step | laptop and the Cohere API |
| M3 | seeds 1 and 2 trained, adapters and exports back on the laptop | both exports hashed in the PREDICT file | desktop |
| M4 | six decodes and grades on the 206, the ceiling instrument, the 33 specifications, the laptop bar; the choice; the held-out 182 read once | all five conditions written with receipts | laptop |
| M5 | release engineering: `dawnr-6.0-*.gguf` and `dawnr-6.0.sha256` beside the kept v5 manifest, `release/DATA-dawnr-6.0.json`, the full 6.0 card, README, SCOREBOARD, `docs/MEASURED.md`, `release/ROLLING.md`, CITATION.cff as dawnr 6.0.0, `VERSION` 6.0.0, `SHA256SUMS` and signature, tag `v6.0.0` with the rolling tag moved to it | a clean checkout on a second machine reproduces the card's table with `t/reproduce.sh`; CI green on the tag | laptop |
| M6 | the update to Cohere Labs for the release, and the final report | the entry in `internal/COHERE-GRANT-UPDATES.md` and the user's "sent" | none |

Cohere Labs gets an update at every incremental release (the condition of the permission) and a drafted entry at
every milestone (the user's rule of 2026-10-24).

## 8. Naming and files

- Model files: `dawnr-6.0-0000N-of-0000M.gguf`, `dawnr-6.0.sha256`, `LICENSE-dawnr-6.0`, `NOTICE-dawnr-6.0`. The
  `student` names stay on the v5 files for reproduction and are not reused.
- Documents: `release/MODEL-CARD-dawnr-6.0.md` (a stub until M5), `release/DATA-dawnr-6.0.json`, the 6.0 PREDICT
  file, receipts `release/evidence/6.0-*.json`.
- `VERSION` reads `6.0.0-dev` until M5 sets `6.0.0`; `dawnr version` prints it.
