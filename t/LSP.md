# t/LSP.md -- the t language server (ROADMAP 15.2)

`t/lsp.py` is one server, spoken to over stdio in the Language Server
Protocol: JSON-RPC 2.0 messages framed with a `Content-Length` header,
exactly as any LSP client library already expects. Any editor that can
launch a subprocess and talk stdio LSP can use it; the server does not
know or care which editor is on the other end.

## Running it

    export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$PATH
    python3 t/lsp.py

It reads JSON-RPC from stdin and writes JSON-RPC to stdout; nothing is
printed to stdout that is not a framed message (diagnostics, errors and
tracebacks go to stderr). The PATH export matters only once a client
triggers `t/verify` or a `didSave` (see VERDICTS below) -- diagnostics,
hover, definition and formatting need no kernel at all.

An editor's LSP client configures the server command as `python3
<repo>/t/lsp.py` with no arguments, `initializationOptions` optional (see
below), and points it at `.t` files.

## initializationOptions

    {"kernels": ["dafny", "verus", ...]}

The kernel set `t/verify` and the automatic post-`didSave` verify run
against. Defaults to `["dafny"]` when omitted -- fast enough to keep the
committed transcript (below) a quick test; a client that wants the full
seven-kernel picture passes its own list here, or per-call in a `t/verify`
request's own `params.kernels`.

## What each request returns

- **initialize** -- capabilities: `textDocumentSync: 1` (full sync only:
  every `didChange` sends the whole new text, not incremental edits),
  `hoverProvider`, `definitionProvider`, `documentFormattingProvider`.
- **textDocument/didOpen, didChange, didSave** -- notifications, no reply.
  Each one re-parses the document's current text with `surface.parse(text,
  positions=...)` and runs `check_wf.check_wf` with that positions map,
  then sends `textDocument/publishDiagnostics` for the document: one
  `Diagnostic` per `WfError` (or, if the text does not parse at all, one
  `Diagnostic` for the `SurfaceError`). Each diagnostic's `range` starts at
  the offending TOKEN's own position -- the same (line, col) `check_wf`/
  `surface.py` attribute the error to, converted from t's 1-based
  convention to LSP's 0-based one -- and runs to that token's own end
  (see `_token_span` in lsp.py: exact for every name, an approximation
  covering the leading keyword/operator for a compound node). `code` is
  the rule key (a `check_wf.RULES` entry) or the parse error's SYNTAX.md
  production; `source` is the literal string `"t"`.
- **textDocument/hover** -- `null` if the document does not parse or the
  cursor is not on a name; otherwise a markdown hover: the name, its type,
  and its kind (`param`, `return`, `local`, `spec_fun`, or `bound` for a
  `forall`/`exists` variable), plus the declaration's own `file:line:col`
  when the name has one (every kind but `bound`, since a quantifier
  variable's only "declaration" is the quantifier itself). `range` covers
  the name under the cursor.
- **textDocument/definition** -- `null` unless the cursor is on a call to
  a `spec_fun`, in which case a `Location` at that `spec_fun`'s own `spec
  fun <name>(...)` declaration line.
- **textDocument/formatting** -- one `TextEdit` replacing the whole
  document with `surface.print_task`'s output (the printer's own
  canonical form), or `[]` if the document does not currently parse
  (formatting a broken file is a no-op, not a crash: nothing runs a
  printer over an AST that does not exist).
- **t/verify** (custom request) -- `{"started": true}` immediately; the
  actual result arrives afterward as a `t/verdicts` notification (below).
  `params`: `{"uri": <document uri>, "kernels": [<kernel>, ...]}`
  (`kernels` optional, defaults to the server's own set).
- **shutdown** -- `null`. **exit** -- no reply; the process exits.

## The `t/verdicts` notification

Sent automatically after every `didSave`, and once per `t/verify` request,
after the kernel run finishes -- ROADMAP 15.1's `tlib.verify`, run in a
background thread so the server keeps answering every other RPC while a
kernel is working (a real kernel run can take several seconds per side).

    {"uri": <document uri>,
     "kernels": {
       "<kernel>": {
         "status": "ok" | "absent" | "no_twin",
         "provisional": <bool>,
         "real": <Outcome string> | null,
         "twin": <Outcome string> | null,
         "twin_op": <string> | null,
         "witness": <string>,
         "source_sha": <string> | null,
         "kernel_version": <string> | null,
         "cached": <bool>
       }, ...
     }}

- `status: "absent"` -- the kernel binary itself is missing on this box
  (`tlib.kernel_version` raised). `real`/`twin` are `null`. An absent
  kernel is reported as absent here; it is never given a verdict of any
  kind, invented or otherwise.
- `status: "no_twin"` -- the kernel is present but no rung of the twin
  ladder produced a witness for this task (`harness.twin_cached`
  returned `None`). `real`/`twin` are `null`; the reason is not carried
  separately here (the diagnostics/well-formedness side is a task's
  contract; the twin ladder's own refusal reasons are `tlib`'s, read
  through `tlib.explain` if a client wants the sentence).
- `status: "ok"` -- `real` and `twin` are `verifiers.Outcome` strings
  (`"verified"`, `"refuted"`, `"vacuous"`, `"malformed"`, `"timeout"`,
  `"unproved"`, `"tool_error"`). `provisional` is `tlib.verify`'s own
  flag: a flake_check that ran but its n runs did not all agree -- an
  editor should show this verdict as unconfirmed, not final. `cached` is
  true exactly when both the real and twin sides came from `t/cache.py`
  (this call ran no kernel at all); it is the one field in this payload
  that depends on process history rather than the task's content, which
  is why the committed transcript test (below) masks it out of the
  comparison.

## The committed transcript

`t/lsp-transcript.jsonl` is one recorded session, `python3 t/lsp.py` as a
real subprocess, over `t/tasks/abs.t` (well-formed) and
`t/malformed/wf-unbound.t` (parses, fails `check_wf` with two errors):
`initialize`, `initialized`, `didOpen` on each file (diagnostics
published: empty for abs.t, two `WfError`s for the malformed file), a
`hover` on abs.t's parameter `x`, a `definition` at that same position
(null: a param reference is not a `spec_fun` call), a `formatting`
request, a `didSave` on abs.t (diagnostics republished, then a
`t/verdicts` notification for the `dafny` kernel), `shutdown`, `exit`.
Each line is `{"dir": "c2s" | "s2c", "msg": <the JSON-RPC message>}`, in
the exact order sent and received.

`t/test_lsp.py` replays it: starts the real server, sends every `"c2s"`
message in order, and after each one reads as many `"s2c"` messages as
the transcript recorded there, asserting each actual reply equals the
recorded one field for field (masking only `t/verdicts`' `cached` flag;
every verdict word, kernel name, outcome string, source hash and kernel
version is compared exactly). A second, transcript-independent check
takes every `publishDiagnostics` message the transcript recorded and
asserts its diagnostics' `range.start`s are exactly the (line, col) pairs
`surface.check_file` reports for that same file, converted to LSP's
0-based convention -- the DONE WHEN's other half, "every diagnostic lands
on the token 14.2 names".

Run: `python3 t/test_lsp.py` (needs the kernel PATH export above, since
replaying the transcript's `didSave` step drives a real `dafny` run
through `t/verify`'s automatic post-save trigger).

## One real exchange

`textDocument/hover` at line 1, character 9 (0-based) of `t/tasks/abs.t`
-- 1-based (2, 10), the `x` in `task abs(x: int) returns (r: int)`:

request:

    {"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover",
     "params": {"textDocument": {"uri": "file:///.../t/tasks/abs.t"},
               "position": {"line": 1, "character": 9}}}

response:

    {"jsonrpc": "2.0", "id": 2,
     "result": {
       "contents": {"kind": "markdown",
                    "value": "**x**: `int` (param)\n\ndeclared at file:///.../t/tasks/abs.t:2:10"},
       "range": {"start": {"line": 1, "character": 9},
                "end": {"line": 1, "character": 10}}}}

A `spec_fun` call gives a richer example (not part of the committed
transcript, which stays on abs.t, but reproducible against any task with
one, e.g. `t/tasks/gcd.t`'s `ensures r == gcds(a, b)`): hovering the
`gcds` call reports `kind: "spec_fun"`, `type` the spec_fun's own result
type, and a declaration position on its `spec fun gcds(...)` line;
`textDocument/definition` at that same position returns a `Location`
there instead of `null`.
