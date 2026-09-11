# t for VS Code: walk-through

2026-09-11. Written against `t/editors/vscode/` at this commit, on the
Dell box (`cs-rahman-dell`, Linux, no display -- see the note at the
bottom of this file for exactly what that means for who can run which
part). ROADMAP 15.3's DONE WHEN names this file: "from a fresh checkout
on Linux and on Windows the committed walk-through yields every
behaviour in the usability half of the bar." ROADMAP 15.5's DONE WHEN
also points here: "the walk-through shows a task VERIFIED with its twin
REFUTED, a real task REFUTED with the kernel's message, and an absent
kernel, and the same task shows the same verdicts in AGREEMENT.md."

## 0. Prerequisites

- VS Code 1.85+.
- Python 3.12 on PATH as `python3` (Linux/macOS) or `py -3.12` (Windows,
  RUN-ON-WINDOWS.md: the bare `python`/`py -3` names can resolve to an
  older interpreter on a box with more than one installed).
- At least one kernel installed (t/README.md; RUN-ON-WINDOWS.md for the
  five-native-kernel route on Windows, or WSL2 for all seven). This
  walk-through was measured with `dafny` present and `verus` forced
  absent (step 6) to show both doors in one session.
- Node 22 only to BUILD the `.vsix` (`npm install && npx @vscode/vsce
  package` inside `t/editors/vscode/`); a person installing the built
  `.vsix` needs no Node at all.

## 1. Install the extension

```
cd t/editors/vscode
npm install
npx @vscode/vsce package
```

produces `t-notation-0.1.0.vsix` (measured on this box, this session:
473556 bytes, 322 files -- see "Measured on this box" below for the full
`vsce package` transcript). In VS Code: Extensions view -> "..." menu ->
"Install from VSIX..." -> pick the file. Or from a terminal with the
`code` CLI on PATH: `code --install-extension t-notation-0.1.0.vsix`.

Open the repository root as a VS Code workspace (`code /path/to/tup`).
Set, if the defaults do not already fit:

- `t.pythonPath`: `python3` (Linux/macOS) or `py` with the workspace's
  own launch args, or the full path to a 3.12 interpreter.
- `t.serverPath`: default `t/lsp.py`, resolved against the workspace
  root -- already correct for this repository's own layout (`t/lsp.py`
  next to `t/cli.py`), change only when `t/` is opened as the workspace
  root itself, in which case set it to `lsp.py`.
- `t.kernels`: defaults to all seven; narrow it to what is actually
  installed (`README.md`/`RUN-ON-WINDOWS.md` say what each platform has).

## 2. Open a task, introduce an error, see the diagnostic at the token

Open `t/tasks/abs.t`. Diagnostics start empty (14.2/14.3: a well-formed
file has none). Change `ensures r >= 0` to `ensures r >= 0 and`, an
incomplete `and` with a missing right operand, and save. The extension's
client relays `textDocument/publishDiagnostics` from `t/lsp.py`
unchanged; VS Code underlines starting at the offending token. Measured
on this box, the equivalent `check_wf`/parse error for that edit, through
the same code path the server uses:

```
$ python3 t/cli.py check /tmp/.../abs-broken.t
/tmp/.../abs-broken.t:3:7: Expr: expected an expression after 'and', found '{'
```

(one line, `file:line:col: production: message`; `t/COMMAND.md`'s `check`
section documents the format). Revert the edit.

## 3. Hover a param and a local

Hover the `x` in `task abs(x: int) returns (r: int)` (line 2, the `x`
starting at 1-based column 10). Measured through the same server
subprocess the extension spawns (`python3 t/lsp.py` over stdio,
`textDocument/hover`, exactly `t/lsp-transcript.jsonl`'s own recorded
exchange, replayed by `t/test_lsp.py` on every run):

```json
{"contents": {"kind": "markdown",
              "value": "**x**: `int` (param)\n\ndeclared at file:///.../t/tasks/abs.t:2:10"},
 "range": {"start": {"line": 1, "character": 9}, "end": {"line": 1, "character": 10}}}
```

`abs.t` has no local (only params and a `returns` name), so the local
case is measured on `t/tasks/digit_sum.t` instead (`t/test_lsp.py`'s
`test_hover_on_local_declaration`, this session):

```
test_hover_on_local_declaration: hover at 11:7 -> m int declared at {'line': 11, 'col': 7}
```

-- a `var m: ...` local, hovered at its own name, answers with its type
and points at its own declaration line (not the `var` keyword; this was
a 15.2 fix: see ROADMAP.md's 15.2 DONE paragraph).

## 4. Format

Command Palette -> "Format Document" (or save with format-on-save). The
extension relays `textDocument/formatting`, one `TextEdit` replacing the
whole document with `surface.print_task`'s canonical form -- for
already-canonical `abs.t` this is a no-op (`t/lsp-transcript.jsonl`'s own
recorded formatting reply reproduces the file byte for byte).

## 5. Save and watch the verdicts view fill: VERIFIED / REFUTED per kernel, with the witness

Saving `abs.t` triggers `t/lsp.py`'s automatic post-`didSave` `t/verify`
run (a background thread; `t/LSP.md`). The "t verdicts" view (activity
bar icon) fills with one row per kernel in `t.kernels`; the status bar
shows the agreement count. Measured by driving the real server the
extension's `LanguageClient` drives (`python3 t/lsp.py`, stdio,
`initializationOptions.kernels: ["dafny", "verus"]`, `didOpen` +
`didSave` on `t/tasks/abs.t`), this session:

```json
"dafny": {
  "status": "ok", "provisional": false,
  "real": "verified", "twin": "refuted", "twin_op": "collapse-if",
  "witness": "x=1 -> real 1, twin -1",
  "kernel_version": "dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2"
}
```

The verdicts-view row this renders: **dafny: verified / refuted
(collapse-if)** with a tooltip carrying the witness verbatim,
`witness: x=1 -> real 1, twin -1` -- the input assignment `t/LSP.md`'s
`witness` field already sends, rendered as text, no reinterpretation
added by this extension.

## 6. An absent kernel

`t.kernels` including a name not installed shows `absent`, never a
verdict. Every one of the seven kernels this box owns happens to be
reachable through `verifiers/discover.py`'s glob-under-`$HOME` door
(README.md), so demonstrating a genuine absence here meant overriding
one kernel's own environment-variable door to a path that does not
exist (`T_VERUS_BIN=/nonexistent/verus`, `discover.py`'s resolution
order: the env var, when set, always wins over PATH and the glob) --
the same session as step 5, same `initializationOptions.kernels:
["dafny", "verus"]`:

```json
"verus": {
  "status": "absent", "provisional": false,
  "real": null, "twin": null, "twin_op": null,
  "witness": "none", "kernel_version": null
}
```

The verdicts-view row: **verus: absent** -- no verdict word, no
witness, exactly the rule ROADMAP 15.5 names ("an absent kernel shown
as absent and never as a verdict").

## 7. A task whose real is REFUTED -- measured 2026-09-11

`t/editors/examples/wrong_abs.t` is `abs` with a false postcondition
(`ensures r >= 1`, which fails at `x = 0`, `r = 0`). Graded once, exactly
the command this walk-through's task named:

```
$ python3 t/cli.py verify t/editors/examples/wrong_abs.t --kernels dafny
dafny: REFUSED, real is refuted, the kernel found this wrong; collapse-if twin is refuted, the kernel found this wrong
```

(exit 1.) **This is `refuted`, the bar's own clause, measured through the
full pipeline.** `t/harness.py` gained `real_witness(task)`: the same
bounded interpreter search `twin_cached`/`interp.Reference` already run,
turned on the REAL body itself instead of a real-vs-twin comparison --
does the real body's own value violate its own `ensures` (or is the body
undefined) at some `requires`-admitted input? For `wrong_abs`,
`x = 0` gives `r = 0`, which fails `ensures r >= 1`. `t/tlib.py`'s
`_verify_one` and `t/run_par.py`'s `lower_and_dispatch` now lower the
REAL with that witness (`lower_fn(task, task["body"], witness=real_witness(task))`)
exactly the way they already lower the twin, so a real that is genuinely
wrong gets the same refutation certificate a wrong twin gets, and reads
`refuted` with the certificate's own message
(`t_refutation_certificate (correctness): Correct`, `dafny`'s own
`verifiers.dafny.verify` extras). `real_witness` returns `None` for
every one of the 34 committed tasks (`t/test_real_witness.py`), so no
correct task's real verdict moves. The t/verdicts-shaped payload
measured for this file, same session as steps 5-6 (via `tlib.verify`,
which is what `t/lsp.py`'s worker calls):

```json
"dafny": {
  "status": "ok", "provisional": false,
  "real": "refuted", "twin": "refuted", "twin_op": "collapse-if",
  "witness": "x=1 -> real 1, twin -1",
  "real_witness": "x=0 -> real 0, twin 0",
  "kernel_version": "dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2"
}
```

(`tlib.verify`'s entry dict gained `real_witness`, the same
`harness.witness()`-rendered line the twin's `witness` field already was,
one sentence naming the input that makes the REAL's own REFUTED a
verdict about something measured, not asserted. `t/lsp.py`'s own
`t/verdicts` JSON-RPC payload is unchanged by this -- it forwards a
fixed field list from the entry dict and was not touched here -- so
`t/LSP.md`'s documented notification shape needs no edit.) All seven
kernels on this box (dafny, verus, lean, rocq, fstar, spark, framac)
REFUTE `wrong_abs`'s real, measured the same session:
`python3 t/cli.py verify t/editors/examples/wrong_abs.t --kernels dafny,verus,lean,rocq,fstar,spark,framac --json`
prints `"real is refuted, the kernel found this wrong"` in all seven
`message` fields. ROADMAP 15.5's DONE WHEN clause, "a real task REFUTED
with the kernel's message", is measured, not merely rendered.

## 8. Comparing against AGREEMENT.md

`t/AGREEMENT.md`'s `abs` row, `dafny` column: `verified / refuted`.
Step 5's measured `t/verdicts` payload for the same task and kernel:
`real: "verified"`, `twin: "refuted"` -- the same two words, same order,
same task. This is the comparison ROADMAP 15.5's DONE WHEN asks for
("the same task shows the same verdicts in AGREEMENT.md"), and it holds
for the one cell this box can measure both ways.

## What a person running this on a real display needs to check

Every step above through the raw `t/lsp.py` JSON-RPC traffic, the
`.vsix` build, `t/test_vscode.py`, and the two CLI greps is measured on
this box (`cs-rahman-dell`, headless: no display, so no VS Code window
runs here, only the language server subprocess it would drive). What
is NOT measured here, and is the open clause of both ROADMAP 15.3 and
15.5, is **the VS Code window itself: the diagnostic underline actually
rendering at the token in the editor, the hover popup, the "Format
Document" command, the "t verdicts" TreeView and status bar item
actually painting the rows above, and the whole sequence repeated on
Windows** -- run by a person on Linux and on Windows, per this file's
own steps 1-8, on a box with a display.

## Measured on this box, this session (2026-09-11)

```
$ node --version && npm --version
v22.23.2
10.9.8
$ which dafny
/usr/local/bin/dafny
$ npx @vscode/vsce package
...
 DONE  Packaged: t-notation-0.1.0.vsix (322 files, 462.46 KB)
$ python3 t/test_vscode.py
test_package_json_declares_language: language 't', grammar ./syntaxes/t.tmLanguage.json, settings t.pythonPath/t.serverPath/t.kernels, command t.verify -- all present
test_grammar_covers_keywords_and_string_methods: 29 KEYWORDS and 16 STR_METHODS entries all named in the grammar's patterns
test_extension_js_is_valid_javascript: node --check extension.js OK
test_vsix_if_built: t-notation-0.1.0.vsix (473556 bytes) is a zip containing extension/package.json
OK
$ python3 t/test_lsp.py
test_transcript_replays: 10 client messages, 9 server replies, each matching the recorded transcript
test_diagnostics_match_check_file: 2 diagnostic(s) across the transcript, every range.start == check_file's (line, col)
test_hover_on_local_declaration: hover at 11:7 -> m int declared at {'line': 11, 'col': 7}
OK
```
