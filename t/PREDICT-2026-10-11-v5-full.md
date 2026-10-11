# Full v5 source recovered: rebuild before another GPU run

Registered after recovering the historical input and before assembling or training the new candidate.

The original 5,095-row input is now recovered from an offline archive. Its full SHA-256 matches the
October 5 record: `848fca29d9399ef91fcb867006e4ff42f60b53e9e2e084e4f1e93dae37811110`.
The [recovery receipt](out/v5-rebuild-20261011/desktop-source-recovered.json) records independently
verified copies on the control node and lab. This resolves the input blocker in
[the earlier registration](PREDICT-2026-10-11-v5-rebuild.md).

## The data rule

Start with the complete historical six-kind mixture, preserving its original rows. Run
`student_rows.py` over the proved corpus and retain additional specification-given examples only
when they are not already represented. Add the 22 newly verified teacher rows through the existing
English and `spec_first_rows.py` routes, using the original mixture's s2 problem prompt. Record
distinct additions separately from derived views of the same problem; repeated rows are not corpus growth.

Keep the existing 200 programming questions and 33 specification questions fixed. Filter the
assembled data through `heldout_audit.py --refuse-gpl` and `spec_panel.py check`, then repeat the
audits on the final bytes. The first audit will remove overlaps even with problems already removed
from historical panels; the final file must also pass the published `--panels` gate. Retain the
original source separately so every removal is traceable.

When a row is refused, remove other views of the same identified problem as well. In particular,
a Python-only row must not survive solely because the specification checker examines t blocks.
Measure this with a real-data control before implementing that assembly step. Preserve anonymous
rows only under the existing gates; do not invent a common identity for unrelated unnamed rows.

**D1:** at least 4,000 rows remain eligible before the token-length filter, with all six historical
row kinds represented. Fewer rows or a missing kind falsifies D1; it does not justify relaxing a gate.
Publish the original contribution, fresh specification rows, new teacher contributions, duplicates,
family removals, audit findings and token-length exclusions separately.

## Training and comparison

Use the v5 recipe: the same pinned Qwen3.5-4B base, QLoRA NF4 with double quantisation and bf16 compute,
all-linear rank 64 / alpha 16 / dropout 0.1, learning rate 2e-4, five epochs, maximum 2,845 tokens,
seed 1 and reference linear-attention kernels. Freeze the exact data beside the adapter with the
new `student_sft.py` input-preservation path. No GPU is allocated until the data gates pass and
token counts support a bounded cost estimate. Record the chosen price, deadline and total cap
before allocation. A budget-limited incomplete training run is not a completed candidate.

Compare Q8_0 models with the fixed single-greedy protocol already registered for v5: same server,
prompts, context, token budget, tests, seven kernels and specification gates. Report clean-200 and
all 33 as requested, clean-182 as the programming panel of record, and the recovered clean-14
specification subset once its identity has been checked. This does not reproduce the historical
17-call route. The unpublished teacher4/v6 artifacts are prior evidence, not a new successful release:
their Q8 reading was 20/33 and failed that run's release rule.

**F1:** the full-data candidate gains at least one all-seven problem on clean-182 over the current
matched v5 reading. A tie or loss falsifies F1. **F2:** it does not lose an all-seven answer on the
clean-14 specification subset. Report paired gains and losses. An unqualified overall win also
requires no regression on the requested full-33 specification count; improvements on a clean
subset remain explicitly qualified. No release changes on the strength of an incomplete run.

These panels have been used before. This experiment measures this candidate on fixed panels;
it is not independent confirmation. The exact data and resource receipts precede training.

Sources read before assembly: the recovered teacher2/teacher3 pool builders, specgiven/build_v5.sh,
teacher4's pool/finalize records, the failed v6 release reading, `student_rows.py`, `graded_pool.py`,
`spec_first_rows.py`, `heldout_audit.py` and `spec_panel.py`.

## Rebuild measured before allocation

**D1 failed:** 3,352 rows survive the gates, with all six kinds still present. The
[assembly receipt](out/v5-full-20261011/build-inputs.json) starts with the exact 5,095 original rows
and appends 139 specification-given rows, 14 English answers and 27 specification/Python proof views.
Another 337 corpus rows, eight of the 22 English answers and 39 derived views duplicate existing
prompt/answer pairs. These are not new examples.

The [removal receipt](out/v5-full-20261011/family-removals.json) removes 1,923 rows: the union of
1,111 directly flagged rows, 14 split exclusions and 812 additional views of refused problems.
The resulting file retains 3,266 original rows, 60 new corpus rows, nine new English answers and
17 new derived views. Both forms of `heldout_audit --refuse-gpl` pass, and the fixed 33-question
specification check reports zero matches. The [summary](out/v5-full-20261011/data-summary.json)
links these counts to the saved input identity; no panel was reduced to obtain a pass.

The family removal is a measured correction. On task 227, the existing specification checker
refuses the t answer but leaves its Python-only sibling. The
[new helper](recipes/student_row_families.py) removes both through their shared problem identity.
Seven controls pass, including unrelated and anonymous rows, invalid identities, bad finding
indices and missing reference data; the [real-data receipt](out/v5-full-20261011/family-control.json)
records the original Python escape and its removal.

An intermediate 1,528-row result was invalid: the restored reference pool lacked the APPS file,
and pool membership silently removed 2,381 rows. Restoring the archived data expands the pool
from 882 to 3,148 entries, with every previous entry unchanged
([reference receipt](out/v5-full-20261011/reference-recovery.json)). The helper now refuses a
missing reference for an otherwise eligible training identity. The restored data is isolated
from the ongoing matched evaluation. The invalid attempt is preserved separately.

The [exact token accounting](out/v5-full-20261011/tokenization.json) retains **3,319 rows** at
2,845 tokens and drops 33: 595 English, 380 Python, 548 specification, 590 proof/Python,
503 specification-given and 703 repair examples remain. They contain 1,934,065 input tokens
per epoch. Scaling the earlier 2,462.9-second L4 run by tokens gives 7.55 hours; scaling by
squared sequence lengths gives 11.33 hours. These are planning estimates, not measured training
times for this candidate.

The full audited input is [saved here](out/v5-full-20261011/train-rows.jsonl), SHA-256
`443b674393f5f6a87178b74010f6901cd4cfe0f80a12423880518485aaa2e717`.
The [build and audit recipe](recipes/v5-full-2026-10-11-rows.sh) and
[token-count recipe](recipes/v5-full-2026-10-11-tokenize.py) reproduce these stages from the
registered sources. Training has not begun at this registration.

## Resource bound registered before allocation

Use one on-demand `g2-standard-8` L4 in `us-central1-a`, with a **14-hour maximum lifetime**,
native scheduled instance deletion, automatic restart disabled and a 100 GiB auto-deleting
boot disk. The control-node watcher also deletes it once artifacts are safe. No second VM,
unbounded retry or deadline extension is part of this run.

The posted [G2 price](https://cloud.google.com/products/compute/pricing/accelerator-optimized)
checked October 11 is $0.853624312 per hour: at most $11.96 compute for 14 hours. Set a
**$15 run budget**, reserving $0.50 for disk, $0.10 for the external address and $1.84 for
up to eight GiB of exported artifacts and control traffic. The disk reservation exceeds the
listed [balanced-disk cost](https://cloud.google.com/compute/disks-image-pricing); the network
reservation uses the [published network rates](https://cloud.google.com/vpc/network-pricing).
Record actual lifetime and artifact bytes afterwards; these are bounds from posted rates,
not an invoice or a billing-account spending limit. The final adapter and Q8 export are copied
once from the VM and then distributed from the control node. A traffic guard terminates the
VM if the eight-GiB allowance is exhausted.

Five epochs and the registered v5 recipe stay fixed. An incomplete run at the deadline is a
budget failure, not a completed model. Once the adapter and Q8 export are safe, remove the VM
and disk; the matched CPU evaluation can continue without a GPU bill.
