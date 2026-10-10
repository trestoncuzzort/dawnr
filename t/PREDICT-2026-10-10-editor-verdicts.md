# T79: bind editor verdicts to the document that was checked

Registered before the new scheduling and client probes, from `fb237a0`.
Source inspection found three related gaps: the worker reads the server's
mutable kernel list after scheduling; it publishes results without checking
whether the document changed or closed; and the VS Code agreement count includes
provisional verified/refuted entries.

Predictions: a deferred explicit Lean request can run Dafny after handle_verify
restores the defaults; a delayed result for old text can appear after an edit,
close/reopen or a newer request; and a provisional entry increases the displayed
agreement count. The client also has no document version or text digest to
reject a notification already in flight when the user edits.

Bars: controlled worker scheduling reproduces these failures before repair;
workers use their captured kernel set and only the latest request for a still
current open document may publish. Notifications carry the checked document
version and UTF-8 text SHA-256, distinct from each kernel's lowered-source hash.
The client displays only matching results for its active document, clears old
results on edit/close/switch, and never counts provisional outcomes. Cover an
edit-and-revert and close-and-reopen so comparing text or version alone is not
mistaken for request identity. Preserve the existing real LSP transcript test,
updating its expected additive identity fields explicitly.

Prior work: `t/lsp.py`, `t/LSP.md`, the recorded transcript, the VS Code client,
and T75's library provisional-verdict repair. The Language Server Protocol's
versioned document identifiers and diagnostic versions bind asynchronous
results to document state:
https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/.
Node tests will exercise the real client module with VS Code API stand-ins;
they do not establish a live editor UI walkthrough.

All seven server scheduling tests failed before repair, including an edit
performed while a fake kernel was running. The first eight client controls
failed seven cases; only the ordinary confirmed result passed. The repaired
server snapshots kernels and document identity, invalidates older request
tokens on edits/close/reopen/new requests, and serializes publication with state
updates. It also handles didClose and clears that document's diagnostics.

The client matches version and UTF-8 text hash, retains separate still-current
results for open documents, refreshes on editor switches, and excludes
provisional results from agreement. One initial switch test did not actually
switch its active document; that fixture was corrected to exercise a different
document, with a further positive control for switching back. Unversioned
notifications are refused. Node 22.23.3 was installed from a checksum-verified
official archive to execute these controls.

Fifteen affected Python tests pass, including the actual recorded stdio session,
and all ten JavaScript behavior controls pass. The transcript adds the actual
checked document version/hash; its kernel verdict, source hash and version
expectations were retained. Clean checkout `dee973d` repeated all 15 affected
tests, including the ten JavaScript cases. Source hashes, command and Node
archive identity are in `t/evidence/2026-10-10-editor-verdicts.json`. A live VS
Code walkthrough remains outside this automated measurement.
