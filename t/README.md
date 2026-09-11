# t

**t is a specification interlingua, not (yet) a programming language.** A task is
written once in t, with a typed signature, preconditions, postconditions and for
now a small body, then lowered mechanically to established verifiers, whose kernels
supply every verdict. t itself proves nothing and is trusted for nothing; that is
the design, not a temporary weakness. The trust always bottoms out in a kernel
with decades of adversarial history (today: Dafny 4.11.0 / Z3; next: Verus,
SPARK, the WS-7 tier-A list).

Prior art this stands on rather than beside: Why3 (one spec language, many
provers) and Viper (one intermediate verification language, many frontends).
If t ever grows its own checker, that checker gets verified inside Rocq or Lean
(the CakeML path) before anything trusts it, since a homemade language certifying a
homemade system is two unaudited instruments signing each other's receipts, and
it is refused here in advance (ROADMAP.md, "The far field").

## v0, honestly scoped

- Types: `int`. No arrays, no quantifiers, no heap, no loops. v0 exists to prove
  the pipeline, task to lowering to kernel verdict to witness, not expressiveness.
- A task is committed as JSON (`tasks/*.json`); that was the whole rationale
  while it held: no parser to write means no parser to trust. Since
  2026-09-04 a surface notation exists on top of it (`surface.py`,
  `SYNTAX.md`), so the reasoning now runs the other way: the parser is
  trusted because its round trip against the committed JSON is measured,
  not because it doesn't exist.
- `lower_dafny.py` emits Dafny; `dafny verify` decides. Exit codes as measured
  on 4.11.0: 0 verified, 2 malformed, 4 could-not-prove, which reads UNPROVED
  (TIMEOUT on "out of resource"). Until 2026-09-02 exit 4 was read as refuted;
  it is not a countermodel and is no longer read as one
  (WITNESS-2026-09-02-dafny-door.md).
- Every lowering also emits a BROKEN TWIN (the body's first `if` collapsed to
  its then-branch). A task only counts when the real lowering VERIFIES **and**
  the twin is REFUTED: one witness for "the spec is provable," one for "the
  spec has teeth." Since 2026-09-02 the twin's REFUTED means the kernel accepted
  a certificate lemma restating the measured witness, not a bare failing exit.
  A twin that still verifies is a vacuous spec and the task is
  refused. This is dafny_pairs.py's measured-flip rule, applied to t from birth.

## Files

| File | What it is |
|---|---|
| `SPEC.md` | The v0 task format and expression grammar, complete. |
| `lower_dafny.py` | t → Dafny lowering + twin generation + verdict collection. |
| `tasks/` | Tasks in t. |
| `out/` | Lowered .dfy files and verdicts (regenerated; witnesses are committed). |

2026-09-11 (ROADMAP 14.1): the line above calling a task JSON is the v0
description; it is no longer how a task is written or stored. `t/tasks/`
now holds `.t` files, the surface notation SYNTAX.md documents and
`surface.py` parses and prints; the JSON this file still calls the format
is the AST that notation parses to, derived from the `.t` text and never
edited by hand. `run_all.py`, `run_par.py` and `grade.py --tasks DIR` read
the `.t` files through `tasks_io.py`; a directory with none (a
spec-experiment run's own generated `tasks/`) is still read as `*.json`.

2026-09-11 (ROADMAP 14.4, "One command"): `python3 t/cli.py <subcommand>`
is now the one entry point for a person or an editor working on a single
task, with `parse`, `check`, `format`, `lower`, `verify`, `twin` and
`explain` subcommands over `surface.py`, `check_wf.py`, `tlib.py` and (for
`verify` on a whole directory) `run_par.py`'s own `probe_backends`,
`lower_and_dispatch` and `format_table`, so `verify t/tasks` writes
byte-identical `AGREEMENT.md` (modulo the timestamp line). Text output by
default, `--json` for JSON Lines (one record per diagnostic: file, line,
col, rule, severity, kernel, message), documented with a real example per
subcommand in `t/COMMAND.md`. `cli.py` is new; it edits none of
`surface.py`, `check_wf.py`, `tlib.py`, `harness.py`, `names.py` or
`run_par.py`.

2026-09-11 (ROADMAP 15.3/15.5, VS Code): `t/editors/vscode/` is a plain
JavaScript extension (no TypeScript build) with a TextMate grammar
(`syntaxes/t.tmLanguage.json`, covering every `surface.KEYWORDS` and
`surface.STR_METHODS` entry, checked by `t/test_vscode.py`), a client
that starts `t/lsp.py` over stdio via `vscode-languageclient`, settings
`t.pythonPath`/`t.serverPath`/`t.kernels`, and a "t verdicts" TreeView
plus status bar item fed by the `t/verdicts` notification (15.5: real
and twin per kernel with the witness rendered as text, `absent` for a
missing kernel, `(provisional)` marked). `npm install && npx @vscode/vsce
package` produced `t-notation-0.1.0.vsix` (473556 bytes) on this box,
user-local Node 22 (`~/.local/opt/node`), no changes to `t/lsp.py`,
`t/cli.py`, `t/harness.py`, `t/run_par.py` or any lowering. This box has
no display, so the VS Code window itself (diagnostics rendering, hover
popups, the TreeView painting) is unverified here; `t/editors/
WALKTHROUGH.md` measures everything reachable without one, including the
finding that `tlib.verify`'s REAL side is certificate-gated the same way
`t/verifiers/dafny.py` and `t/verifiers/fstar.py` document (REFUTED only
via a refutation-certificate lemma, which only the TWIN lowering carries)
and so cannot itself read `refuted` for any task, a gap in ROADMAP 15.5's
DONE WHEN as currently reachable through `cli.py verify`/`t/lsp.py`.
