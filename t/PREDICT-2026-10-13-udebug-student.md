# A student on execution-verified judge rows (registered 2026-10-13T05:17Z, before any model call)

## What this run is

The Python lanes of `t/PREDICT-2026-10-12-udebug-teacher.md` left 1,048 execution-verified rows on 909 UVa
train problems (`kind: judge-python`, `proof: none`: a program that reproduces every stored case of its
problem), and 377 held-out judge questions nobody has answered with a local model. This run is one
ReST-EM iteration (Singh et al., arXiv:2312.06585: sample, keep what the oracle accepts, fine-tune the base
once) on those rows, beside the proof rows the 10-11 run trained on, and it measures what a 4B student
does on the held-out judge questions before and after. The 10-11 run (`t/PREDICT-2026-10-11-gcp-student.md`)
is the template: same base, recipe, card and bounds; its own student is the control.

## Data, frozen before training

- `t/out/udebug-student-2026-10-13/train-rows.jsonl`, SHA-256
  `1bebb99c69e1b58863c39507d7ce5b7d9f617918e1c21a2f1d063f436740b2fb`: the 406 audited rows of the 10-11
  run (331 specification-given, 75 English; their file SHA-256 `0248cf93...`) plus **909 judge-python rows,
  one per problem**, chosen by lane in the order DeepSeek-V3.2 scale (60), DeepSeek pilot (3), Qwen3-235B
  (843), Qwen3-Next (3), from `t/out/udebug/rows-judge-python.jsonl` (SHA-256 `56fdf656...`). Build record:
  `build-inputs.json`. The held-out questions are a hash split of the bank by problem (seed 1338), so no
  training row shares a problem with a question.
- `judge-heldout.jsonl`, SHA-256 `8704ca97d1a3c64997f2dac5ab7199415b442f80eef9382e156e41a510b60ede`: the
  377 held-out judge questions, each with the teacher's own prompt and its tests directory.
- The two row audits of the 10-11 run (`heldout_audit.py --panels --refuse-gpl`, `spec_panel.py check`) run
  on the final file and their exit status is recorded beside it before training; they remove rows, never
  questions.

## Training and the answers

Base `Qwen/Qwen3.5-4B` revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, the v5 recipe in
`t/student_sft.py` exactly as on 10-11 (NF4 with double quantisation, bf16 compute, all-linear LoRA rank 64 /
alpha 16 / dropout 0.1, learning rate 2e-4, five epochs, seed 1, batch 1 with 16 accumulated, maximum 2,845
tokens, response-only loss, overlength rows counted and excluded). The adapter is merged into the
unquantised base in bf16 for every answer.

Answers, all greedy, one per question, at most 1,024 new tokens, under the model's chat template with
thinking off (`t/udebug_student.py --backend hf`, which writes the teacher's sample layout so
`t/udebug_gate.py` grades them unchanged on every stored case under the memory cap):

- **A, the base**, on the 377 judge questions.
- **B, the 10-11 student** (adapter SHA-256 `50a51ca0...` merged into the same base), on the 377: the control
  for "proof rows alone".
- **C, this run's student**, on the 377, and on the 33 specification questions of the 10-11 run
  (`student_generate.py`, the same `s1` prompt), graded on the lab with all seven kernels by the 10-11
  grading recipe. The 232 programming IDs follow only if the VM's time allows; otherwise they are recorded
  as not run, not scored.

## Card and bounds

Project `dawnr-core-2026` (GPUs-all-regions 1, L4 1 in us-central1, both unused at registration), one
`g2-standard-8` with one L4 in `us-central1`, 100 GiB auto-delete boot disk, no service account, no
automatic restart, provider termination six hours after creation with `instanceTerminationAction: DELETE`,
the same pinned Google PyTorch image and package pins as 10-11. **Budget: $10 planned exposure** (six hours at
the posted $0.8536 an hour is $5.12; the rest covers disk, address and the transfer of one adapter and one
export). Results are copied off and the VM is deleted explicitly as soon as the work ends; the deadline
survives a lost controller.

## Predictions, with what falsifies each

- **P1, the base:** between 10% and 40% of the 377 questions judged correct on every stored case. *Falsifier:*
  below 10% ⇒ the base cannot follow the io contract, and the comparison is about formatting; above 40% ⇒
  reported as such (the teachers sit at 36-62%).
- **P2, the control:** the 10-11 student within 5 points of the base. *Falsifier:* a gap above 5 points either
  way ⇒ proof rows alone move judge Python, reported with its sign.
- **P3, the student:** at least 10 points above the base. *Falsifier:* less ⇒ one iteration on 909 rows does
  not transfer to held-out problems, and the next lever is k > 1 per problem or a second iteration, not a
  bigger first one.
- **P4, no regression on the proof panel:** at least 10 of the 33 specification questions prove in all seven
  kernels with refuted twins (10-11: 21 of 33). *Falsifier:* 9 or fewer ⇒ the judge rows cost the
  specification skill, reported with the matrix.
- **P5, time:** five epochs on 1,315 rows, both control answers and the student's answers complete inside the
  six-hour lifetime (10-11: 130 steps in 41 minutes for 405 rows). *Falsifier:* an incomplete adapter or an
  unanswered question set.
- **P6, cost:** at most $10 by the posted rate and wall time.

One seed cannot establish a recipe; the installed release stays v5 whatever the read says. Every refusal
carries its reason (differing line, exception, timeout, no fence, token cap).

## Inputs frozen and audited (2026-10-13T05:19Z)

- `heldout_audit.py --panels --refuse-gpl` on the final file: 1,315 rows, 736 distinct t programs (0 did not
  parse), **0 rows flagged**; 38 rows match problems already outside the panels
  (`decontamination-rows-2026-10-05.json`), not refused. Exit 0 (`audit-final.json`, `audit-final.log`).
- `spec_panel.py check` against the 33 specification questions: **0 rows match a question**. Exit 0
  (`spec-audit-final.json`, `spec-audit-final.log`).
- The judge rows are Python programs, not t tasks, so the lineage audit's program checks apply to the 406
  proof rows and the panel checks to every prompt; no row was removed by either audit.
- The VM is created with a provider termination time of **2026-10-13T11:18:05Z** (`vm-termination-time.txt`),
  six hours after the launch request.

## Read

(filled in after the run)
