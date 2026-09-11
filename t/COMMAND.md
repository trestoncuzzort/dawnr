# t/cli.py: one command

ROADMAP 14.4, "One command", 2026-09-11. `python3 t/cli.py <subcommand> ...`
is the single entry point for everything an editor or a script needs from
t on one task or one tasks directory: `parse`, `check`, `format`, `lower`,
`verify`, `twin`, `explain`. Standard library only, argparse; runs the
same way on Linux, macOS and Windows (`py -3.12 t\cli.py ...`, see
RUN-ON-WINDOWS.md's `--flag=value` note, which applies here unchanged).

Every subcommand prints text for a person by default; `--json` switches
to JSON Lines, one JSON object per line, per diagnostic, with exactly the
keys `file`, `line`, `col`, `rule`, `severity`, `kernel`, `message`.
`severity` is one of `error`, `warning`, `info`, `verdict`. `line`/`col`
are JSON `null` wherever a record is not about one AST node; `kernel` is
`""` wherever a record is not about one kernel.

Every flag also accepts the `--flag=value` form (argparse's own long
option syntax) as well as `--flag value`; e.g. `--kernel=dafny` and
`--kernel dafny` are the same call. See `t/test_cli.py`'s
`FlagEqualsFormTest` for the one test this is measured by.

Exit codes: 0 nothing wrong; 1 at least one diagnostic of severity
`error`, or at least one verdict that is not the counted flip
(`verified`/`refuted`); 2 a usage problem (a bad flag, an unknown kernel
or verdict word).

Every example below is a real run pasted verbatim, from `t/` on this
machine, 2026-09-11 (`export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$PATH`
first, as every kernel-touching command in this repo requires).

## parse

Text to the canonical JSON AST (or, on a bad file, the parse diagnostic).

```
$ python3 cli.py parse tasks/abs.t
```
```json
{
  "body": [
    {
      "if": {
        "cond": {
          "args": [
            {
              "var": "x"
            },
            {
              "int": 0
            }
          ],
          "op": "<"
        },
        "else": [
          {
            "assign": [
              "r",
              {
                "var": "x"
              }
            ]
          }
        ],
        "then": [
          {
            "assign": [
              "r",
              {
                "args": [
                  {
                    "var": "x"
                  }
                ],
                "op": "neg"
              }
            ]
          }
        ]
      }
    }
  ],
  "ensures": [
    ...
  ],
  "name": "abs",
  "params": [
    {
      "name": "x",
      "type": "int"
    }
  ],
  "requires": [],
  "returns": [
    {
      "name": "r",
      "type": "int"
    }
  ],
  "t": 0
}
```

On a malformed file (`t/malformed/stmt.t`, `r := 5 := 0;` shape a
statement never starts with), `--json` prints the SurfaceError as one
diagnostic and exits 1:

```
$ python3 cli.py parse malformed/stmt.t --json
{"col": 3, "file": "malformed/stmt.t", "kernel": "", "line": 4, "message": "'5' does not start a statement", "rule": "Stmt", "severity": "error"}
```

## check

Parse, then `check_wf`: well-formedness diagnostics.

```
$ python3 cli.py check tasks/abs.t
tasks/abs.t: well-formed, no errors
```

```
$ python3 cli.py check malformed/wf-arith-int.t --json
{"col": 10, "file": "malformed/wf-arith-int.t", "kernel": "", "line": 3, "message": "+ over non-int", "rule": "arith-int", "severity": "error"}
```
(exit 1)

## format

The printer's canonical text; `--write` rewrites the file in place, and
is idempotent (running it twice produces byte-identical output the
second time, `t/test_cli.py`'s `test_write_is_idempotent`).

```
$ python3 cli.py format tasks/abs.t
t 0
task abs(x: int) returns (r: int)
  ensures r >= 0
  ensures r == x or r == -x
{
  if x < 0 {
    r := -x;
  } else {
    r := x;
  }
}
```

## lower

The lowered source for one kernel, or every kernel with `--kernel all`;
to stdout by default, or to `--out DIR` as `<task>.<suffix>` per kernel.
The rename comment (`names.rename_comment`) is included automatically by
every lowering when a task's identifiers collide with the target
language's keywords; `abs` needs no renames, so none appears.

```
$ python3 cli.py lower tasks/abs.t --kernel dafny
method Abs(x: int) returns (r: int)
  ensures (r >= 0)
  ensures ((r == x) || (r == (-x)))
{
  if (x < 0) {
    r := (-x);
  } else {
    r := x;
  }
}
```

`--kernel all --out DIR` writes `abs.dfy`, `abs.rs`, `abs.ads`, `abs.c`,
`abs.lean`, `abs.v`, `abs.fst` under `DIR`.

## verify

On one file: through `tlib.verify`, one diagnostic per kernel.

```
$ python3 cli.py verify tasks/abs.t --kernels dafny
dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong
```
(exit 0: the flip counted)

On a DIRECTORY, this runs the identical pipeline `run_par.py`'s `main()`
does -- `probe_backends`, `lower_and_dispatch`, `format_table` -- so the
table it writes is byte-identical to `run_par.py`'s own, modulo the
timestamp line. This is the one full-matrix run this item is allowed:

```
$ python3 cli.py verify tasks --jobs 12 --table /tmp/claude-1004/.../scratchpad/command-agreement.md
...
7 kernels, 34 tasks: DISAGREEMENT, see /tmp/claude-1004/.../scratchpad/command-agreement.md
EXIT=1
```

(exit 1 is expected and correct: DISAGREEMENT means at least one cell did
not flip, exactly what `run_par.py`'s own exit code means for the same
34-task corpus -- `min_max x rocq` and `min_max x fstar` timed out and
`split_join x rocq`/`split_join x fstar` came back unproved on this run,
the same kind of finding `run_par.py` itself reports, not a `cli.py`
defect.)

Then, diffed against the committed `t/AGREEMENT.md` with the timestamp
line stripped from both sides (2026-09-11, this run):

```
$ diff <(tail -n +2 AGREEMENT.md) <(tail -n +2 /tmp/claude-1004/.../scratchpad/command-agreement.md)
$ echo "diff rc=$?"
diff rc=0
```

**Empty diff.** `python3 cli.py verify t/tasks --jobs 12` produced
`AGREEMENT.md` byte-identical to `run_par.py`'s own, modulo the
timestamp line, over all 7 kernels and all 34 committed tasks. This is
the ROADMAP 14.4 DONE WHEN bar for `verify`, measured, not assumed.

## twin

The ladder's chosen operator and its witness, or the named refusal.

```
$ python3 cli.py twin tasks/abs.t
collapse-if, witness: x=1 -> real 1, twin -1
```

## explain

One sentence per kernel for an outcome word (`verified`, `vacuous`,
`refuted`, `malformed`, `timeout`, `unproved`, `tool_error`; verifiers'
own vocabulary, `verifiers.Outcome` / `tlib._OUTCOME_SENTENCE`), or one
line for `--kernel K` alone.

```
$ python3 cli.py explain refuted --kernel dafny
dafny: refuted is refuted, the kernel found this wrong
```

## Interpretation note on `explain`

The bar reads "explain (a verdict word, optionally --kernel K: one
sentence per outcome per kernel from tlib.explain and harness's
vocabulary)". `tlib.explain` itself takes a `verify()` entry (a dict with
`real`/`twin`/...), not a bare outcome word, and this item may not edit
`tlib.py` to add a second entry point. `cli.py explain WORD` therefore
reads the word directly against `tlib._OUTCOME_SENTENCE` (the same table
`tlib.explain` itself reads from, verifiers' own vocabulary, nothing
invented here) and prints it once per kernel (or once, for `--kernel K`),
which is the literal "one sentence per outcome per kernel" the bar asks
for when the outcome is given as a bare word rather than a full verdict
entry. `cli.py verify --json`'s per-record `message` already uses
`tlib.explain` on a real entry for a task that was actually run, which is
where a caller gets the entry-shaped form.
