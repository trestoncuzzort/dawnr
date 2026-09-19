# Witness: all seven kernels on a second Mac, and the Dell's table reproduced

Recorded 2026-09-16 (the runs ended 2026-09-17 00:35Z). `internal/MACHINES.md`
listed this machine as "New. Kernels to install." and named the bar: an
install counts when `run_par.py` on the committed tasks matches
`t/AGREEMENT.md`, 30 of 34 in all seven. It does. The install itself, with
every deviation from the 2026-09-06 route, is on `RUN-ON-MACOS.md` under
"A second Mac, 2026-09-16".

## The machine

    macOS 26.6.2 build 25G83, Apple M3 Max, 14 cores (10 performance, 4
    efficiency), 36 GB unified, Xcode 27.0 (27A266a), Apple clang 21.0.0
    Python 3.12.10 via uv at ~/.local/bin/python3.12; python3 on PATH is 3.14.6

## The seven kernels, as the adapters resolved them

| Kernel | `version()` | Resolved at |
|---|---|---|
| Dafny | `4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2` | `~/.local/dafny/dafny` (release zip, bundled z3 4.12.1) |
| Verus | `0.2026.08.30.b432e82` | `~/.local/verus/verus-arm64-macos/verus` (rustup 1.29.1, toolchain 1.97.1-aarch64-apple-darwin) |
| GNATprove | `FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git` | `~/.local/gnatprove/gnatprove-aarch64-darwin-16.1.0-1/bin/gnatprove` |
| Frama-C | `33.0 (Arsenic) / alt-ergo 2.4.3-free` | `~/.opam/default/bin/frama-c` (opam switch on Homebrew's OCaml 5.5.0; why3 1.8.2) |
| Lean | `4.33.1, arm64-apple-darwin24.6.0, commit 819816b2e0a3` | `/opt/homebrew/bin/lean` (elan proxy to `~/.elan`) |
| Rocq | `The Rocq Prover, version 9.2` | `/opt/homebrew/bin/coqc` |
| F\* | `2026.08.30, platform=Darwin_arm64, compiler=OCaml 5.3.0` | `~/.local/fstar/fstar/bin/fstar.exe` |

Every version string matches `t/AGREEMENT.md`'s kernel list. Seven of seven
resolved with no `T_*` variable set; checked with the adapters, not with
`command -v`.

## The matrix, three measurements

`~/.local/bin/python3.12 run_par.py --jobs 8 --table <elsewhere>`, 34 tasks
by 7 kernels, 238 cells, diffed cell by cell against the committed
`AGREEMENT.md` (the Dell's, 2026-09-15 20:29Z).

**Run 1, 00:02:52Z to 00:12:54Z (10 minutes).** 6 of 238 cells differ; 25 of
34 in all seven against the Dell's 30. Four are `framac` reading
`tool_error / tool_error` on `filter_pos`, `reverse`, `swap` and `tail`, the
seq-returning tasks. Cause, found by rerunning WP with `-wp-msg-key prover`:
why3 1.8.2 does not recognise the version string `2.4.3-free`, so WP had
registered Alt-Ergo with an empty version and the SMT-LIB driver meant for
2.5 and later, and 2.4.3's psmt2 frontend answers `Syntax error` on the
polymorphic `define-fun` (`eqmem`) those four tasks emit. `RUN-ON-MACOS.md`
has the `~/.why3.conf` entry that fixes it; `frama-c -wp-list-provers` before
reads `Prover Alt-Ergo [Alt-Ergo:] (alt-ergo) (counter-examples)`, after
`Prover Alt-Ergo 2.4.3 [Alt-Ergo:2.4.3] (alt-ergo)`. The other two cells are
`framac` on `divmod_pair` reading `timeout / refuted` and `spark` on `min_max`
reading `verified / timeout (FLAKED)`, both timing cells (`verifiers/spark.py`
and `verifiers/framac.py` name these two kernels as the load-sensitive ones).

**Run 2, 00:14:06Z to 00:31:27Z (17 minutes), after the why3 fix.** 1 of 238
cells differs: `spark` on `min_max` again reads `verified / timeout`. 30 of 34
in all seven, the Dell's number. The run took longer than run 1 because the
`spark` column landed last, so its cells ran eight at a time with the six
concurrent kernel calls per cell that `run_par.py` describes: 48 gnatprove
trees on 14 cores, load average 95. That is the 96-prover regime the Dell
flaked in, scaled to this box.

**The one cell alone, 00:34:32Z, 75 seconds.** `cli.py verify --kernels spark
--flake 3 tasks/min_max.t` with nothing else on the CPU: `verified /
refuted`, three of three. That is the re-measurement `verifiers/spark.py`
documents for its r20 timeouts (alone at `--jobs 2 --flake 3`), and it
closes the last difference: every one of the 238 cells has now been read on
this Mac as the Dell reads it.

The final line of both full runs was `7 kernels, 34 tasks: DISAGREEMENT, a
finding`, exit 1, as the Dell's is: four committed tasks do not read all
seven anywhere (`count_vowels`, `split_join`, `swap_rows`, `min_max` on the
Dell; here `min_max` was the load cell and `count_vowels`, `split_join`,
`swap_rows` read exactly as committed).

## What to run on this machine

`--jobs 8` is fine for six of the seven columns and wrong for `spark`. Until
`run_par.py` orders cells so `spark` is spread over the run instead of
finishing it, use `--jobs 2` for a table meant to be compared, or `--jobs 8`
and re-measure any `spark` or `framac` timeout alone. `internal/MACHINES.md`'s
"start with 2 jobs and measure" stands.

## Also done this session

- `reproduce.sh` no longer hardcodes the lab workstation's home: it `cd`s to
  its own directory and resolves the corpora through `$T_CORPORA`, defaulting
  to `<repo>/t-corpora`, the same rule `corpora.py` applies. The two tests
  that named `$HOME/tup/t/out/lifted-tasks` (`test_lower_dafny_closure.py`,
  `test_lower_rocq_loop_cert.py`) now look beside themselves; they skip here
  as before because the lifted corpus is not committed.
- `t/lab.py` opened on this machine (Homebrew python@3.12 with python-tk@3.12,
  torch 2.14.0 with Metal in `~/.venv-t`) and showed run 2's cells live from
  `T_WATCH`.
- DafnyBench cloned to `<repo>/t-corpora/DafnyBench` (785 ground-truth
  programs); `corpora.py` resolves it with no configuration.
