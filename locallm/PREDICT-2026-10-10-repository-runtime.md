# Repository runtime boundary, 2026-10-10

The supported workflow is inspecting, editing and testing repository code. Host
settings, desktop programs and services are outside that workflow. This change
uses the existing repository sandbox and file journal rather than introducing
another execution mechanism. Sources read before implementation: DAWNR-AGENT.md,
DAWNR-HARNESS.md, internal/RESEARCH-2026-10-07-zoom-out.md and
locallm/PREDICT-2026-10-01-agent-on-the-base.md.

Predictions, before regression runs:

1. Default sessions expose no `pc` tool. Old `system: true` configurations fail
   explicitly, before a host action can start.
2. Calling the retained compatibility refusal for `pc`, including detached calls,
   starts zero processes even if a caller supplies permissive policy or approval.
3. Configured compile/test commands require the repository sandbox. Missing or
   failed bubblewrap never falls back to a host command.
4. Read-only diagnostics and repository file changes still pass their existing
   regression controls. Any regression falsifies this preservation claim.

The tests use temporary repositories and mocked host runners. Real sandbox tests
are reported separately from skips when this machine cannot create namespaces.

Additional prediction, registered before its targeted run: a repository-local
executable named `df` or `bash`, placed first on PATH, cannot turn a `sysinfo`
read into a host command. Existing command PATH filtering will be shared with
host diagnostics. The temporary-fixture negative control must leave its marker
absent; the baseline is expected to create it.

## Outcome

All four retirement predictions hold in the regression suites. The additional
PATH prediction failed before its fix: both the repository `df` and `bash`
fixtures wrote their marker through `sysinfo`. Diagnostics now use the same
repository-filtered PATH as command configuration, including shell lookup; both
markers remain absent after the change.

Runs (Python with pytest; no model server or cloud calls):

- `python -m pytest -q locallm/test_repository_runtime.py locallm/test_dawnr_cli.py locallm/test_dawnr_agent.py`:
  **147 passed, 2 skipped**. The skips are the two existing path-string-walk race
  tests, whose implementation explicitly has a check-then-open window. Real Linux
  bubblewrap controls ran, including network separation, outside-write refusal,
  and child-process cleanup.
- `python -m pytest -q locallm/test_repository_runtime.py locallm/test_dawnr_shell.py locallm/test_dawnr_tasks.py`:
  **58 passed**. This includes overlay and copy sandbox modes, legacy host-call
  refusal, file changes and replay of historical task judgments. The two sandbox
  failure controls cover a missing executable and refused namespace creation.
- `python -m pytest -q locallm/test_harness.py locallm/test_harness_adversarial.py locallm/test_harness_chat.py locallm/test_agent_eval_native.py locallm/test_dawnr_warm.py`:
  **91 passed**, retaining explicitly configured extension behavior.
- Python compilation, `bash -n bin/dawnr`, and `git diff --check` passed.

The first suite runs exposed old assertions that expected unsandboxed execution
or a redirect to `pc`; those expectations were replaced with refusals. A timeout
control also compared a sandbox PID with an unrelated host PID, so it now checks
that the child's heartbeat stops. Independent positive controls invoke only
those tests' temporary scripts directly, outside the supported agent API.

These measurements cover the runtime boundary, not model accuracy or the safety
of arbitrary trusted MCP servers, hooks or skill scripts. The diagnostic command
allowlist remains an allowlist, not a proof that every utility is read-only.

## Review follow-up prediction

Two external code reviews were treated as untrusted hypotheses. One report points
to a concrete regression: valid read-only diagnostics whose command starts with a
file reader can be routed from `sysinfo` to sandboxed `sh`. Before the regression
run, the prediction is that `cat /proc/version`, `head -n 5 /proc/meminfo`, and
`cat /etc/os-release` are all accepted by the diagnostic allowlist but routed to
`sh` by the current front door. After restoring the read-only classification
check, all three must stay on `sysinfo`; a repository file read must still route
to `sh`. Retired `pc` calls must remain refused.

### Review outcome

The three registered routing controls all failed before the fix, with `sh` where
`sysinfo` was required. Restoring the `look(command) is None` guard fixed them.
Repository file reads still route to `sh`, and legacy `pc` calls stay rejected.
`python -m pytest -q locallm/test_repository_runtime.py locallm/test_dawnr_cli.py`:
**45 passed**. Diff whitespace checks passed.

Of eight external review reports, one reproduced. The other seven were rejected
against the implementation, rather than accepted because the model was confident:

| Review | Report | Read against the code |
|---|---|---|
| Qwen | missing-sandbox denial can bypass `wrapped` | `run_command` and `preview` both return immediately on `_gate` denial; directly calling `wrapped` also refuses |
| Qwen | `exec_path` reaches diagnostics unsanitized | `register_agent` computes `safe_exec_path` before passing it; repository and relative entries are removed |
| Qwen | `look` resolves commands through ambient PATH | `look` parses allowed command shapes; execution explicitly uses the filtered PATH |
| Qwen | `pc` is rerouted to `sysinfo` | `route` returns an obsolete `pc` name immediately, so the absent tool is refused |
| DeepSeek | preview versus execution has inconsistent exceptions | both supported paths return the same gate refusal before reaching `wrapped` |
| DeepSeek | an agent without bubblewrap can still run shell commands | the shell is omitted and configured commands refuse; file-only operation remains intentional |
| DeepSeek | direct diagnostics using `os.defpath` is unexpected | that is the intentional conservative default; configured sessions supply the filtered PATH |
| DeepSeek | file-shaped valid diagnostics are routed to `sh` | reproduced on three commands and fixed with the regression controls above |
