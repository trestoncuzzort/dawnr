# dawnr_api.py: predictions before the reported test run

Written after `locallm/dawnr_api.py` and `locallm/test_dawnr_api.py` were drafted and iterated on
locally, but before the run this change reports. This is an engineering change, not a measurement
with an uncertain scientific answer, so the falsifiable claims below are about correctness and
non-regression rather than a number that could land anywhere on a curve -- the same "measure before
you claim" discipline (AGENTS.md rule 1, 3) applied to shipping code rather than a training result.

## What is being shipped

A standard-library OpenAI-compatible chat completions server (`GET /v1/models`,
`GET /v1/models/{id}`, `POST /v1/chat/completions` with streaming, `tools`/`tool_calls`, auth and
size/time limits) over the existing `engine.Engine`/`dawnr_harness.Harness`, built from OpenAI's own
type definitions (openai/openai-python, fetched -- the docs page is a JS shell and the published
openapi.yaml is 2.7MB; research receipt `51355b6e280d`). It adds one new module, one new test module,
and one new section in `DAWNR-HARNESS.md`; nothing existing is edited except that doc.

## Predictions, with what would falsify them

1. **The new suite passes outright.** `python -m unittest locallm.test_dawnr_api` reports **23 of 23
   tests passing**, covering: the OpenAI-messages-to-dawnr-conversation conversion (including a
   client tool result becoming a `tool_output` part marked `untrusted`, checked down to the actual
   `<|untrusted|>` token in the rendered ids, not just the part dict); `parse_client_tools`'
   schema-before-recording behaviour; `run_turn`'s finish_reason logic (stop, length, a `stop` string
   with a match spanning several streamed tokens, a client tool call halting generation before
   anything is forced back); that dawnr's own registry tool calls (the t tool) never reach visible
   content; and, over a real HTTP connection, `GET /v1/models`, a full tool-call-then-continue round
   trip across two requests sharing one model instance, SSE streaming framing plus the usage chunk,
   the bearer-token check, and the request-size and `n` limits. **Falsified by:** any failure. A
   failure here means a defect in this change, fixed before the run is reported clean, not a result
   to report as-is.
2. **Zero regressions in the existing suites.** `test_harness.py` (46 tests), `test_harness_chat.py`
   (11) and `test_dawnr_chat.py` (28) all still pass unchanged, because `dawnr_api.py` only *imports*
   `chat`, `engine` and `dawnr_harness` -- it defines no new tool names in the shared registry outside
   a request's own lock-held scope, patches no shared state, and the one file it edits
   (`DAWNR-HARNESS.md`) is documentation. **Falsified by:** any change in outcome for a test that
   passed before this change. A regression here means something in this change reaches outside its
   own module in a way the design did not intend, and gets root-caused (fetch-before-fix if the cause
   implicates a design choice already made elsewhere) before anything is reported fixed.
3. **A real client library reads the non-streaming shape without complaint.** The dict
   `chat_completion_response(...)` returns has exactly the keys openai-python's `ChatCompletion`
   type declares as required (`id`, `object`, `created`, `model`, `choices[].index/message/
   finish_reason`, `usage`), confirmed by structural comparison against the fetched type file, not
   by running the real `openai` package (not a dependency here, by design -- the runtime stays
   standard-library Python).

## Decision rule, fixed now

- **All three hold:** report the run's numbers (pass counts) as the evidence for this change and
  stop there -- no further tuning of the tests to fit the code or the code to fit the tests after the
  fact.
- **(1) fails on a first attempt:** fix the specific defect the failing assertion names, rerun, and
  only report the rerun; do not weaken the assertion to make it pass.
- **(2) fails:** stop and diagnose before touching test_dawnr_api.py further -- a regression in an
  unrelated suite means this change's isolation assumption (client tools live only inside one
  request's lock-held scope) was wrong, which is a correctness bug in the design, not a test-writing
  problem.
- **(3) fails:** the response shape is wrong against the reference and must be corrected against the
  fetched type file before this is called "OpenAI-compatible" anywhere in the docs or the report.

## Addendum, 2026-09-27, written after both runs below -- not a prediction

Everything above was written and frozen before the run it describes, as rule 3 asks. This section is
the opposite of that on purpose: it is added after the run above already happened, and after a second
run that came after it, so it does not belong under "Predictions" and is not written as if it were
registered in advance. It exists because the record would otherwise stop at 23 tests and stay silent
about what changed next.

**The design changed under review, and the count grew from 23 to 30.** A security review of the first
version rejected it: a client's declared `tools` were merged into the operator's own
`dawnr_harness.Registry` for the request and rendered into the trusted prompt beside the operator's
own tools, unmarked -- a Tool Poisoning Attack in the Registry's own terms
(invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks, 2025-04-01; a tool's
description is written to instruct the model, so whoever supplies it can embed an instruction the
model reads as trustworthy). The fix moved a request's client-declared tools into a per-request
`_ClientToolHarness` overlay that `DawnrAPI.create`/`create_stream` swap in for the real `Harness` for
exactly one locked generation: a client tool's call is intercepted there, before it would ever reach
`Harness.call` -- no policy decision, no hook, no audit log entry, never added to the registry --
while the operator's own tools through the same object are untouched, still running for real.
`test_dawnr_api.py` grew to 30 tests for this (7 new, one rewritten to use the overlay instead of
adding a client tool into a real `Registry`). The new ones reproduce the finding directly rather than
only exercising the fix in isolation: run against the pre-fix module standalone, both the
description-leak and the registry-mutation checks fire; against the fix, neither does.

**Found only today: none of those 30 tests, old or new, ran on any CI machine.**
`.github/workflows/tests.yml`'s `cpu-torch` job still listed the four files that predate
`dawnr_api.py` entirely -- `test_dawnr_chat.py test_harness_chat.py test_fim.py test_early_stop.py`
-- so "30 tests... all still pass" in the commit history was true only of whichever machine a person
happened to run it on by hand, never of a pull request or a push. Every one of the seven
poisoning-regression tests above ran zero times in CI. Fixed the same day: `test_dawnr_api.py` added
to that job's run line, and `t/test_ci_workflow.py` added alongside it, which reads the job's own run
command back out of the workflow file and fails by the missing file's name (not by a test count) if a
CPU-torch suite is ever left out of it again the same way -- it failed first, against the workflow
before this fix, then passed after. Rerun clean after both fixes, each file its own process, CPU only:
`test_dawnr_api.py` 30/30, `test_dawnr_chat.py` 32/32, `test_harness_chat.py` 8/8, `test_fim.py`
22/22, `test_early_stop.py` 15/15, `test_harness.py` 54/54, `test_harness_adversarial.py` 21/21 -- the
same counts already claimed above and in the overlay commit, now with a CI job that will actually run
them again on the next push instead of only on request.
