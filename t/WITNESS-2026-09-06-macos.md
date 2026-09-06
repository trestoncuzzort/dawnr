# Witness: all seven kernels on macOS, and the Dell's table reproduced

Recorded 2026-09-06. Before this, `ROADMAP.md` said "macOS unmeasured" and
`RUN-ON-WINDOWS.md` said seven kernels on Linux, five native on Windows and
all seven under WSL2. macOS now has seven natively, and the whole agreement
table came back identical to the one measured on the Dell.

## The machine

    macOS 26.6.2, build 25G83, arm64 (Apple silicon), 18 cores, 48 GB
    Python 3.12.10 via uv at ~/.local/bin/python3.12

Python matters: the drivers are 3.12 code and this machine's `python3` is
3.14.7. The suite was run under 3.12.10 explicitly.

## The seven kernels, where they came from and where they were found

| Kernel | Version | Resolved at |
|---|---|---|
| Dafny | 4.11.0 | `/opt/homebrew/bin/dafny` (homebrew, on PATH) |
| Verus | 0.2026.08.30.b432e82 | `~/.local/verus/verus-arm64-macos/verus` |
| GNATprove | FSF 16.1.0, Why3 1.8.2+git | `~/.local/gnatprove/gnatprove-aarch64-darwin-16.1.0-1/bin/gnatprove` |
| Frama-C | 33.0 (Arsenic), alt-ergo 2.4.3 | `~/.opam/default/bin/frama-c` |
| Lean | 4.33.1 (arm64-apple-darwin24.6.0) | `~/.elan/bin/lean` |
| Rocq | 9.2 | `/opt/homebrew/bin/coqc` (homebrew, on PATH) |
| F\* | 2026.08.30, platform=Darwin_arm64 | `~/.local/fstar/fstar/bin/fstar.exe` |

Agda 2.8.0 is also installed at `~/.local/agda/agda`. It is not in the
drivers' `BACKENDS` list, so it takes no part in the table.

Only F\* was installed for this witness, from the upstream release asset
`fstar-v2026.08.30-Darwin-arm64.tar.gz` (tag v2026.08.30), unpacked to
`~/.local/fstar`. The other six were already present. Every version above
matches the pin the project already uses, so this is the same instrument as
the Dell's, not a near neighbour.

## The mistake worth recording

The first pass at this reported "3 of 7 kernels on the Mac". That was wrong,
and the way it was wrong is the useful part: it used `command -v`, which sees
only PATH. Five of the seven are installed under `$HOME` and are found by
`verifiers/discover.py`'s third tier, the home-directory glob, which is the
whole reason that tier exists. The globs already matched this machine's
layout with no configuration: `.local/verus/**/verus`,
`.local/gnatprove/**/bin/gnatprove`, `.opam/*/bin/frama-c`, `.elan/bin/lean`,
`.local/fstar/fstar/bin/fstar.exe`.

Check kernels with the adapters, never with `command -v`:

```bash
cd t && python3 -c "from verifiers.verus import VERUS; print(VERUS)"
```

## The matrix

`python3.12 run_par.py`, 7 kernels x 11 tasks, 77 cells. Result: **71 cells
`verified / refuted`, 6 cells `verified / timeout`, all six Frama-C, all six
on an `invariant-drop` twin over a seq-typed task** (`all_nonneg`, `contains`,
`count_matches`, `linear_search`, `seq_max`, `sum_upto`). Exit 1, because a
disagreement is a finding and the driver refuses to call it agreement.

The final line:

    7 kernels, 11 tasks: DISAGREEMENT, a finding, see t/AGREEMENT.md

## Why AGREEMENT.md was not overwritten

This run reproduced `t/AGREEMENT.md` **cell for cell** against the version the
Dell recorded on 2026-09-05: the same 77 verdicts, the same six Frama-C
timeouts on the same six tasks. The only differences in the whole file were
the timestamp, dafny's build hash suffix, and F\*'s platform string
(`Linux_x86_64` against `Darwin_arm64`).

The committed table was therefore left holding the Dell's Linux receipt and
this file records the reproduction instead. Overwriting a receipt with an
identical one on a different platform destroys the more interesting fact,
which is that both platforms produce it.

That is the claim this witness exists to make: **the seven-kernel matrix is
not a property of the Dell.** The six Frama-C timeouts reproduce too, so they
are a property of Frama-C and the invariant-drop twin over sequences, not of
one box's load.

## What else ran here the same day

The lifter's fast test suite passes on this machine, which it had never been
run on: `test_lift_front` 4 checks, `test_lift_rules` all, `test_lift_check`
all, `test_lift_report` 20. The two groups that need the hand-lifted
`inventory/` seeds skip, because those are the one artifact that cannot be
regenerated from the corpus.

The corpus itself was rebuilt here rather than copied: DafnyBench cloned from
upstream (Apache-2.0, 5.9 MB), `coverage_census.py` over the 785 giving **77
in fragment**, the documented figure, and **25 of the 164 MBPP-DFY**, which is
what ROADMAP WS-13.1 claims. 785 rprints regenerated, 783 clean plus the two
known exit-2 resolve failures.

## Reproducing this

```bash
git clone --depth 1 https://github.com/sun-wendy/DafnyBench.git ~/t-corpora/DafnyBench
cd t && ~/.local/bin/python3.12 run_par.py
```

See `RUN-ON-MACOS.md` for the install side.
