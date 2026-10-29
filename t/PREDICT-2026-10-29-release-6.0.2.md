# Ship the tested verifier and pipeline fixes as dawnr 6.0.2

This patch release includes the imported Frama-C certificate-normalization repair
and the checked internal teacher/data pipeline. Its model manifest is byte-identical
to 6.0.1 and continues to name the three 6.0.0 model files. The new two-seed model
candidate is a separate qualification experiment, still in cloud training.

The concrete verifier bug is a false refusal when Frama-C prints a negated
inequality as an equality. The imported lowering preserves the negation through
a local predicate binding. It changes no assumption or acceptance threshold.
The prior native regression, negative controls, full 114-task Frama-C column and
28-cell seven-kernel control have passed. The matched development control preserves
all per-problem acceptance sets. Those existing measurements remain the evidence
for the repair; final release checks do not replace them.

Before final laptop checks, predict:

1. The existing six-command smoothness workload succeeds for the released 6.0.1
   code and the 6.0.2 candidate using the exact same installed model files and
   server, separate temporary configurations, and a cold start for each.
2. Candidate median command latency and peak memory in use are each within 10%
   of the fresh baseline, with no software thermal slowdown in either run.
3. The release manifest matches the verified 6.0.1 asset byte for byte, and the
   three local model shards match its published SHA-256 values.
4. The standard CI matrix and the clean Ubuntu/macOS install-smoke workflow pass
   at the final release source. Install smoke exercises the published manifest
   after publication; any failure remains visible and requires a fix.

Use the same current smoothness script and repository-description workload for
both application revisions. The baseline uses a detached 6.0.1 checkout through
its temporary environment; record the application version separately from the
harness checkout version. Raw output remains private until paths are removed
from the public receipt. Preserve failed measurements; do not substitute a
favorable retry. The laptop is used only for these final release checks.

Sources: `internal/RELEASE-6.0-PLAN.md`'s operating clarification,
`t/recipes/laptop_smoothness.sh`, `release/evidence/framac-certificate-import-2026-10-25.json`,
`release/evidence/v5-certificate-control-2026-10-25.json`, and
`t/PREDICT-2026-10-25-framac-certificate-binding.md`.
