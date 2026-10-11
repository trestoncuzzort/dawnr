# A capped GPU retrain from the recovered corpus

Registered 2026-10-11 05:39Z, before training or reading any candidate answers.

The complete 5,095-row v5 training file is absent from the restored lab checkout. This run uses the
recoverable proved corpus and new verified answers; it is a new, smaller-data experiment, not a
reproduction of v5. The installed release stays v5 until a candidate passes its release checks.

## Data and gates

[`recipes/gcp-student-2026-10-11-rows.sh`](recipes/gcp-student-2026-10-11-rows.sh) is the build command.
It uses `student_rows.py` to split the 531-document `corpus-r12-headed.txt` at seed 1338: 476 training
documents and 33 specification questions after the established textual exclusions. It offers the
74 recovered English rows and the 22 new DeepSeek rows (nine: 9, b2: 5, b3: 8) alongside them.
Rows outside the current training split are removed and named in `build-inputs.json`.

English rows use `graded_pool.answer_text` and `spec_experiment.build_prompt(..., 's1')`, the existing
student preparation path. The first assembly copied the teacher prompts verbatim: their worked
examples matched held-out specification questions, so `spec_panel.py` rejected every English row.
The corrected preparation keeps the verified answer, renames its task as the question requests,
and removes the teacher's language tutorial and worked examples. Both row audits run afterwards:

- `heldout_audit.py --panels --refuse-gpl`: lineage and behavioural overlap with the fixed problem panels;
- `spec_panel.py check`: overlap with all 33 specification questions, including programs in prompts.

The gates remove training rows, never questions to rescue a score. Both must exit zero on the final
file. The build records input hashes; final row count, hash and retained new rows are recorded before
training. References for all 232 held-out and 100 development IDs must be present. The optional fourth
DeepSeek batch is excluded: there is no finished admitted SFT file for it at registration.

## Training and evaluation

Base: `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
Use the [v5 recipe](../release/MODEL-CARD-student-v5.md) in `student_sft.py`: NF4 with double
quantisation, bf16 compute, all-linear LoRA rank 64 / alpha 16 / dropout 0.1, learning rate 2e-4,
five epochs, seed 1, batch 1 with 16 accumulated, maximum 2,845 tokens, response-only loss.
Count overlength rows rather than truncate them. Use the reference PyTorch linear-attention kernels.
Merge the completed adapter into the unquantised base in bf16.

Generate one greedy answer to each of the 33 specification questions (`score_spec_given.py`, strict
specification preservation), then one greedy `s1` answer to every one of the 232 problem IDs
(`student_generate.py`, maximum 1,024 new tokens). Grade on the lab with all seven kernels and
`T_SANDBOX=landlock`. Report the fixed clean-182 problem panel with larger-input specification
checks; report parsing, tests and each gate separately. A partial set is incomplete, not a whole-panel
score. This single-answer run cannot be compared as if it used v5's 17 answers per problem.

Predictions, falsified at the stated boundaries:

1. Five training epochs complete within the VM's five-hour lifetime; an incomplete adapter falsifies this.
2. At least 10 of 33 specification questions prove in all seven kernels; 9 or fewer falsifies this.
3. At least one clean-182 problem passes tests, the larger-input specification check and all seven
   kernels from its single answer; zero falsifies this.

One seed cannot establish a better training recipe. Do not replace release weights on these results
alone. Save the adapter and evidence even if the predictions fail.

## Compute and cost bound

The selected existing project has open billing attached. A global GPU quota request from 0 to 1 was
approved, and Compute Engine reports 1 available; the selected region also permits one L4.
No production project or account plan was changed.

One `g2-standard-8` in `us-central1` (L4, 8 vCPUs, 32 GiB), 100 GiB balanced boot disk with
`autoDelete: true`, no attached service account, no automatic restart. Set an absolute provider
termination time five hours from launch and `instanceTerminationAction: DELETE`, plus a guest
shutdown timer. Retrieve results and explicitly delete the VM as soon as work ends; verify the VM
and disk are gone. The absolute deadline also survives a disconnected controller.

Run budget: **$10 maximum planned exposure**. Google's fetched price table lists the instance at
$0.853624312/hour in Iowa, or $4.27 for five hours; the remainder covers disk, IP and bounded artifact
transfer. This is a runtime-and-resource bound, not a claim that a billing alert stops charges.
No automatic relaunches or fleet. Save only the adapter, small evidence files and, if needed, one
merged/quantised model export; do not repeatedly transfer base weights.

Sources read before preparing this run: the existing v5 card and row-audit registrations;
[SAFE](https://arxiv.org/abs/2410.15756), [QLoRA](https://arxiv.org/abs/2305.14314),
[Google's GPU quota rules](https://docs.cloud.google.com/compute/resource-usage),
[VM runtime limits](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime),
[quota-project attribution](https://docs.cloud.google.com/docs/quotas/set-quota-project), and
[accelerator pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized).
The local research mirror was absent on the control node; repository research was searched first.

## Inputs frozen before training, 2026-10-11 05:42Z

The final file contains **406 rows: 331 specification-given and 75 English answers**. Six recovered
English rows are excluded by the current split; three normalized answers are duplicates. Of 563
remaining candidates, 81 are removed by the lineage/problem audit and 76 by the specification-panel
audit. Both final audits exit zero. Eighteen of the 22 new answers remain; MBPP 227, 309, 873 and 924
overlap held-out specification functions and are excluded. Every one of the nine-round rows remains.

- Training SHA-256: `0248cf93e57092d91d0f8b6471a22ffae0a5f7aeff337f24bc8604155094fb39`.
- Questions SHA-256: `effc2f4e586e0c4f7638a5a9a2b75515aaf7019de03ca819d46e5aa3d593ab24`.
- [Training and generation script](recipes/gcp-student-2026-10-11-train.sh).
- The lab's row/trainer/audit unit tests: **60 passed**. Its seven kernel version probes pass after
  setting the installed Lean executable explicitly. The legacy whole `preflight.py` still fails on
  its hard-coded remote `~/tup` layout and controller assumptions; it is not reported as passing.
  Its old-v3-prompt warning does not apply to this registered `s1` run.

The VM is live, with a provider-enforced deletion time of **2026-10-11 10:40:06 UTC**, an auto-delete
boot disk and a guest shutdown scheduled five minutes earlier. Training has not started at this entry.

## Preparation checks

Local preflight now follows this checkout, as `lab_mode.sh` already does, and inherits the environment
whose kernel binaries were checked instead of reopening a login profile. The old path and a login
banner had caused false failures. Its full run on the selected audited rows exits zero, with three
named warnings: the old v3 prompt elsewhere in the legacy run scripts, the lab checkout not yet
tracking the newly committed dataset, and its existing tracked edits. This run uses `s1`; the dataset
is committed; evaluator file hashes will accompany the result. The preflight suites pass **27 tests
and 8 subtests** on the lab.

VM environment: the pinned Google image
`pytorch-2-9-cu129-ubuntu-2204-nvidia-580-v20261001`, PyTorch 2.9.1+cu129, Transformers 5.17.0,
PEFT 0.21.2, bitsandbytes 0.50.2 and Accelerate 1.15.0. Two setup failures occurred before training:
the image's TorchAudio 2.11 required a newer PyTorch ABI, and its Jinja 3.0.3 could not render the
model's chat template. The isolated environment now uses TorchAudio 2.9.1+cu129 and Jinja 3.1.6.
See [TorchAudio's compatibility table](https://docs.pytorch.org/audio/stable/installation.html).

Tokenization keeps **405 of 406 rows** (330 specification rows, all 75 English rows), median 396 tokens,
longest retained row 2,069. `vericoding_da0085__findMinimumTotalDistance` exceeds 2,845 tokens and is
excluded whole. The model has 129,859,584 trainable LoRA parameters and the fixed recipe schedules 130 steps.

Evaluation details fixed before any candidate answer: the
[grading script](recipes/gcp-student-2026-10-11-grade.sh) uses 1,000 draws per task with per-task seeds,
completeness at least 0.6, and larger-input checks. It applies MBPP+'s corrected solutions only when
they pass the original problem's tests, the established rule of
[the reference correction](PREDICT-2026-10-02-reference-plus.md). The 378 reference rows come from
`evalplus/mbppplus` revision `b2d74c91837c3f2a20c1299ae98133cbe7cfa077`; the extracted task IDs and
code have SHA-256 `f2fd5d28f85e2911b185bbc720542efdd639bbdd6e43e226afed323fce32f020`.
The [export script](recipes/gcp-student-2026-10-11-export.sh) pins llama.cpp
`23b0202a189c44a54625aadcb37a946dd1d6278d` and writes Q8_0 directly with its converter, without MTP.
The held-out measurements above use the merged bf16 model; they do not establish Q8_0 equivalence.

## Instrument control, registered 2026-10-11 05:54Z

Before candidate generation, replay the 33 supplied correct programs through the same strict
specification-preservation and seven-kernel path (`recipes/gcp-student-2026-10-11-ceiling.sh`).
Prediction C1: all 33 reach grading and at least 30 prove in all seven with refuted twins.
Fewer than 33 reaching grading or fewer than 30 proving falsifies it. This measures the current
instrument ceiling; it changes neither the question set nor the candidate criteria above.

**C1 holds.** The [reference-program control](out/gcp-student-2026-10-11-s1/ceiling-kernels.md)
measured 33 ready questions and 33 proved by all seven, with refuted twins, no missing rows and no
missing twins ([counts](out/gcp-student-2026-10-11-s1/ceiling-levels.json)). It ran 231 cells and
1,386 kernel invocations with the cache disabled. Each question therefore has a solution admitted
by the current toolchain. These are supplied reference programs, not model-generated answers;
the candidate predictions remain unmeasured.

## Training completed

Prediction 1 holds: five epochs, **130 steps in 2,462.9 seconds**, using 405 rows. Final mean training
loss is 0.03635; this is not an accuracy measurement. The completed adapter is saved on the lab and
the control node. Its weights have SHA-256
`50a51ca0f54c1c7986828a08206eae31be8e2900c8656c6ffd345d48d2a2fcf2`.

The final source reconciliation distinguishes representation from additions: 18 of the 22 new
answers are represented, but MBPP 373 duplicates an existing row. Thus **17 distinct new answers**
join 58 retained older English rows and 331 specification rows before the token-length filter.
MBPP 227 and 924 were duplicates too, and both leave with the four held-out overlaps.

The two evaluation panels can run independently: after all 33 specification answers were generated,
their proof checks started while the VM continued the 232 programming answers. A lock serializes
the grading phases. Completed specification results are reused only when the inputs, evaluator,
grading script and output hashes match; the first pass still runs every kernel without the verdict
cache. The initial specification pass was stopped before it wrote a matrix to add this coordination,
then restarted. No model answers or scoring criteria were changed or selected from those partial checks.

## Specification-panel result

Prediction 2 holds: **21 of 33 proved by all seven**, with their twins refuted. In total, 23 proved
by at least one (all 23 also reached three); one failed well-formedness, seven were refuted by at
least one kernel, and two reached no proof. No matrix row or twin is missing. There are no
cross-kernel contradictions (a program verified by one kernel and refuted by another).

The `fib` answer retained a task-level `decreases` clause but supplied an iterative body, which the
language rejects. The strict instrument leaves it rejected. The other failures remain recorded in
the [matrix](out/gcp-student-2026-10-11-s1/spec-kernels.md), with the
[counts](out/gcp-student-2026-10-11-s1/spec-levels.json) and
[stage report](out/gcp-student-2026-10-11-s1/spec-report.json).

The resume guard was exercised on this completed stage: a changed input was refused, restoring the
original input reused the result, and the table stayed byte-identical. Its
[receipt](out/gcp-student-2026-10-11-s1/spec-stage-guard-check.json) records those checks.
The programming-problem result is still pending; no claim of improvement over v5 follows from this panel.

Post-hoc interpretation confirms a concrete contract violation for each of the seven refuted answers.
The [witnesses](out/gcp-student-2026-10-11-s1/spec-counterexamples.json) record admitted inputs, returned
values, failed postconditions and task/interpreter hashes, using `interp.exec_body` and `interp.ev`.
For example, the absolute-value answer returns -1 for -1; both first-match searches return index 1 for
`[1, 1]` and key 1; and `divmod_pair(-1, 2)` returns `(0, -1)`, violating the remainder's lower bound.
These are functional failures. They identify negative inputs and repeated matches as concrete weaknesses
to address with separate training examples; these held-out witnesses remain evaluation evidence.

All eight [CI jobs](out/gcp-student-2026-10-11-s1/ci.json) pass on `f321a718`: the standard-library
suites on Linux, macOS and Windows with Python 3.10 and 3.12, and both CPU PyTorch jobs. The Python
3.10 context-manager compatibility fix lives in dawnr's pytest plugin; the pinned engine tests stay intact.

## Programming answers generated

All 232 registered questions have one answer, generated in 2,103 seconds. The
[generation summary](out/gcp-student-2026-10-11-s1/generation-summary.json) records the stages and
each raw answer's hash. There are 103 parse failures, 30 well-formedness failures and 99 tasks.
Of those tasks, 41 pass the original tests, 49 fail, six exclude a test through their preconditions,
and three produce an undefined result. These are full-232 counts; the clean-182 gated score awaits
the proof matrix and specification checks.

Ten answers reach the 1,024-token cap and all ten fail parsing. The other 93 parse failures stop
naturally. Increasing the token cap alone would leave those 93 failures unresolved. No answer is
repaired or regenerated in this single-answer reading. The final training
[receipt](out/gcp-student-2026-10-11-s1/adapter-run.json) and
[log](out/gcp-student-2026-10-11-s1/run.log) retain the recipe and generation progress.

## Export saved and cloud resources deleted

The lab saved the Q8_0 export and verified its checksum at 07:44:24 UTC. It is 4,482,402,752 bytes,
with SHA-256 `121b3654e74fb088f222da9a5f500a99d88b15663949a6602526d9406b0fa280`.
The [artifact record](out/gcp-student-2026-10-11-s1/artifacts.json) names the base revision, adapter,
export and storage locations. The final adapter has matching checksums on both the lab and control
node. The GGUF is retained on the lab; weights are not added to the source repository.

The [teardown receipt](out/gcp-student-2026-10-11-s1/cloud-teardown.json) confirms that both the VM
and its boot disk return 404 after deletion, observed at **07:45:44 UTC**. The dedicated temporary
VM keys were removed on both machines. Wall time from creation to confirmed deletion was 7,535.5
seconds, well inside the five-hour bound. At the posted VM rate this gives a **$1.7868 compute
estimate**, excluding disk, IP and egress; it is not an invoice. The remaining grading runs on lab
CPUs after cloud teardown.
