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
