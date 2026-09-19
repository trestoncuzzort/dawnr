# Overnight training loop, 2026-09-19

The operator authorized repeated improvement/training rounds, failure diagnosis
and reruns, all available lab resources, stopping lab jobs if necessary, and
pushing updates to GitHub. Expansion is at a stopping point. Model work should
resume only when a round completes, fails or stalls; use a lightweight process
for waiting, and keep reports concise. The broader Phi goal is not achieved.

The active study is `t/out/source-pretraining-2026-09-19` on the lab. Its source
corpus and tokenizer are the corresponding `source-corpus-2026-09-19-v2` and
`source-tokenizer-2026-09-19-v2` directories. Use the lab's `.venv-vllm` Python
for the entire study. Run configuration and six-arm order are fixed in
`locallm/run_pretraining_study.py`; predictions and partition/tokenizer hashes
are in `locallm/PREREG-source-pretrain-2026-09-19.md`. Current core and runner
hashes must remain unchanged while that study is active.

On completion, run `locallm/summarize_pretraining.py` with all six `--run`
assignments (`modern:1337`, `gpt:1337`, `modern:7`, `gpt:7`, `modern:42`,
`gpt:42`). Read every paired result, runtime and failed-attempt record. Report
held-out loss separately from executable correctness. Inspect fixed source-code
completions as the preregistration requires. Save a concise sanitized result and
choose one justified next change; register its prediction before launching.
Keep a comparable control and reuse unchanged completed results only when the
comparison's data, evaluation and training budget are actually identical.

On failure, inspect `study.json`, its named attempt log, `metrics.jsonl` and
available GPU memory. Do not rerun a known failure without a repair or a reason
the condition has changed. `--resume` validates source/data/runtime/checkpoint
identity and skips validated completed arms. If a necessary training-source
change invalidates that identity, preserve the failed study and use a new output
directory with an explicit amendment. Never loosen a gate to turn a failure
into success. Signal interruption is distinct from a model-quality result.

The small event watcher and its endpoint/thread identifiers live in private
local state, not GitHub. After each new launch or same-directory resume, update
its control generation and runner identity. Confirm the watcher is armed, then
end the model turn for the waiting period. A consumed event must not generate
repeated model calls. Failed wake delivery stays visible for retry by the
lightweight watcher. No healthy-run model polling or repeated speculative edits.

Before any new supervised round, refresh hash-bound spec evidence: the stronger
dataset gate currently accepts zero of the previous 210 positive programs
because all lack current explicit evidence. Historical datasets are preserved.
Source pretraining does not use those supervised examples. The proposed new
semantic evaluation is in `locallm/NEXT-semantic-eval-2026-09-19.md`; a held-out
token-loss result cannot substitute for its executable/proof outcome or a
versioned Phi comparison.

Inherited lowering/cache/preflight/lifter changes remain unverified under the
handoff's stated bars. Preserve them and label that status. They are not grounds
for expanding the overnight scope beyond the training/evaluation loop.
