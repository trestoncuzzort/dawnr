# Bedrock review pilot for verification infrastructure

Registered before paid calls. The operator authorized a total AWS budget of
$100 for this work. Start with a $1 proxy budget and a fixed, small request
list; expand only when requests, usage accounting, and useful review output
are observed. All rounds use the same journal, so an increased limit does not
reset prior spending. No cloud machines or GPU training jobs are required.

Use the existing Bedrock adapter after its accounting regressions pass.
Current AWS Price List API entries in us-east-1 were read for Qwen3 235B A22B
2507, DeepSeek v3.2, and GLM 5. Their standard/flex rates match the registered
adapter rates. Initial reviewers: Qwen3 and DeepSeek; maximum 4096 output
tokens, no automatic retry, six requests at most. Request source hashes and
raw responses are retained separately from the accounting journal.

Review three concrete changes: complete PX4 correspondence accounting,
refutation-certificate/Lean helper changes, and removal of built-in host
control. These are public project code, not held-out synthesis problems.
Model findings are hypotheses. No model-generated code is executed, no review
is a proof, and no response enters training data during this pilot.

Bars: each dispatched attempt leaves a durable accounting outcome, even on
failure; at least one reviewer produces specific checkable observations;
any claimed new bug needs a deterministic failing control before a fix.
Existing negative controls and native lab replays decide acceptance. The
pilot's costs, failures, and observations are reported without converting
model agreement into verification evidence.

Sources: existing `t/PREDICT-2026-10-03-teacher-round-bedrock.md`,
`internal/RESEARCH-2026-10-10-verification-next.md`,
[Bedrock pricing](https://aws.amazon.com/bedrock/pricing/), and
[Bedrock cost dimensions](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-understanding-cur-data.html).

Startup notes: the first proxy launch lacked the AWS executable in the service
PATH; the second lacked an AWS region for credential refresh. Both stopped
before serving a request. Six local connection attempts against the stopped
proxy are archived as startup failures; the empty journal and healthy restarted
proxy confirmed zero upstream dispatches. The corrected launch supplies the
absolute CLI path and `AWS_DEFAULT_REGION=us-east-1`. The fixed six-request
pilot then began. These are explicit startup corrections, not automatic
retries of uncertain provider outcomes.

## Outcome

All six fixed pilot requests returned HTTP 200 with recognized default-tier
usage. The durable journal settled all six; no unresolved reservations or
uncertain charges remain. Registered token prices total **$0.02611121**;
AWS billing remains authoritative. The proxy stopped after the batch.
[The manifest](evidence/2026-10-10-bedrock-review/manifest.json) records model,
source/prompt/response hashes, usage and elapsed time, without account data.

The two reviewers produced 23 suggestions across the three contexts. Exactly
one reproduced as a new regression; 22 were rejected after source and test
checks. This small, selected review does not measure general model accuracy.

- Runtime: 1 of 8 reproduced. Read-only `sysinfo` commands recognized by the
  existing allowlist (`cat /proc/version`, `head /proc/meminfo`, and
  `cat /etc/os-release`) were incorrectly routed to the repository sandbox.
  Three new controls failed before the routing guard was restored and passed
  afterward. The runtime/CLI subset then passed 45 tests. Other suggestions
  misread deliberate refusal, existing PATH filtering, or obsolete-tool denial;
  the full disposition is in the repository-runtime prediction record.
- Flight comparisons: 0 of 7 reproduced. Actual prefix-then-exit-zero output
  was refused; malformed numbers returned an output error; nonfinite values
  differed from finite expected outputs. Existing controls reject all-skipped
  domains and never count undefined task results as agreement. Suggestions to
  accept an empty comparison contradict the acceptance rule and were rejected.
- Kernel certificates: 0 of 8 reproduced. Lean checks the conditional lemma
  before any conclusion is usable; real kernel controls and the unchanged full
  column contradict the alleged unsound implication use. SPARK uses the
  intentionally populated Lower instance. Verus charges its production cap of
  64 before expansion and refuses unsupported types. Several reports retracted
  their own claims inside their explanations.

The registered bars hold: every upstream attempt is accounted for, a specific
observation reproduced, and its fix has a deterministic failing-before control.
Review responses were treated as hypotheses throughout; no generated review
code was run and no response entered training data.
