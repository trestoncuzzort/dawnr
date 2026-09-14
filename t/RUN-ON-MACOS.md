# Run t on a Mac

t itself is plain Python 3.12 with no dependencies; the kernels do the
proving. **All seven have native Apple-silicon builds**, and t has run on a
real Mac: 2026-09-06, macOS 26.6.2 build 25G83, arm64, Python 3.12.10, all
seven kernels present, `run_par.py` 7 kernels x 11 tasks in about 8 minutes,
77 of 77 cells matching the Dell's own table exactly. The witness is
`WITNESS-2026-09-06-macos.md`; this page records how to get there.

The honest summary first: macOS is the easiest of the three platforms. Linux
needs a no-root install story, Windows gives five kernels natively and sends
the other two to WSL2, and macOS gives seven, four of them from a package
manager. No WSL2 equivalent is needed and nothing was compiled from source.

## The seven kernels, with where each actually came from

Versions below are the ones measured, and they match the project's pins. Four
come from package managers, three from release tarballs unpacked under
`$HOME`.

| Kernel | Version | How |
|---|---|---|
| Dafny | 4.11.0 | `brew install dafny` (pulls `dotnet@8`) |
| Rocq | 9.2 | `brew install rocq` (provides `coqc`) |
| Frama-C | 33.0 (Arsenic) | `brew install opam`, then `opam install frama-c` |
| Lean | 4.33.1 | elan, then `elan default leanprover/lean4:v4.33.1` |
| Verus | 0.2026.08.30.b432e82 | `verus-0.2026.08.30.b432e82-arm64-macos.zip` from github.com/verus-lang/verus, unpacked to `~/.local/verus/` |
| GNATprove | FSF 16.1.0 | `gnatprove-aarch64-darwin-16.1.0-1.tar.gz` from github.com/alire-project/GNAT-FSF-builds, unpacked to `~/.local/gnatprove/` |
| F\* | 2026.08.30 | `fstar-v2026.08.30-Darwin-arm64.tar.gz` from github.com/FStarLang/FStar tag v2026.08.30, unpacked to `~/.local/fstar/` |

Agda 2.8.0 at `~/.local/agda/agda` is also picked up by its adapter, but Agda
is not in `run_all.py`'s or `run_par.py`'s `BACKENDS` list, so it takes no
part in the agreement table.

The three tarball installs keep their archive and, where upstream shipped
one, its `.sha256` beside the unpacked tree. That costs a few hundred
megabytes and buys the ability to say later which bytes were installed.

## Pointing t at the binaries: usually nothing to do

Discovery tries, in order: a `T_*` environment variable, then `PATH`, then
glob patterns under your home directory. The names, from
`verifiers/discover.py`: `T_DAFNY`, `T_VERUS_BIN`, `T_GNATPROVE`, `T_FRAMAC`,
`T_LEAN_BIN`, `T_COQC`, `T_FSTAR`.

On macOS the third tier does the work with no configuration, because the
globs already describe where these installers put things:

```
verus     .local/verus/**/verus
gnatprove .local/gnatprove/**/bin/gnatprove
framac    .opam/*/bin/frama-c
lean      .elan/bin/lean
fstar     .local/fstar/fstar/bin/fstar.exe
```

Dafny and Rocq come from homebrew and are on `PATH`, so tier two catches
them. Measured on this machine: seven of seven resolved with no `T_*`
variable set.

**Do not check for a kernel with `command -v`.** Five of the seven are not on
`PATH` and never will be; `opam` and `elan` and the tarballs put them under
`$HOME` on purpose. A first pass at this page reported "3 of 7 kernels"
because it asked the shell instead of the adapter. Ask the adapter:

```bash
cd t
python3 -c "from verifiers.verus import VERUS, _VERUS_WHY; print(VERUS or _VERUS_WHY)"
```

The `missing()` message names every place it looked, so a genuine absence
tells you where to put the binary.

## Python: 3.12, not whatever `python3` is

The drivers are 3.12 code. A current Mac's `python3` may be much newer (3.14.7
on the measured machine) and homebrew will keep moving it. Install the pinned
interpreter with uv and call it explicitly:

```bash
uv python install 3.12.10
~/.local/bin/python3.12 run_par.py
```

Everything here is standard library, so there is no virtualenv to make and
nothing to `pip install`.

## The corpus, if you want the lifter too

The kernels alone run the 11 committed tasks. The lifter needs DafnyBench,
which is public and small:

```bash
git clone --depth 1 https://github.com/sun-wendy/DafnyBench.git ~/tup/t-corpora/DafnyBench
```

`corpora.py` resolves `$T_CORPORA` first and falls back to `~/tup/t-corpora`, so
that path needs no configuration either. Missing corpora make the tests skip
with a reason rather than fail. Regenerating the rest of the bank (the
census, the in-fragment list, the rprints) is in `ON-THE-DELL.md`; the one
piece that cannot be regenerated is the hand-lifted `inventory/` seeds.

`nl/` needs `brew install git-lfs` and `git lfs pull`, and costs about 918 MB.

## What running it looks like

```bash
cd t
~/.local/bin/python3.12 run_par.py          # 7 kernels x 11 tasks, about 8 min
python3 test_lifter.py                      # the lifter's fast suite
python3 lift_gate.py                        # the MBPP-DFY fidelity gate
```

`run_par.py` refuses to write a table from fewer than two kernels
(`T_MIN_KERNELS`), names every absent one and where it looked, and exits
nonzero on a disagreement rather than calling it agreement. A partial matrix
is a smaller real measurement, not a failure.

Expect `run_par.py` to exit 1 on this corpus today. Six of the 77 cells read
`verified / timeout`, every one of them Frama-C on an `invariant-drop` twin
over a seq-typed task. That is not a macOS artifact: the Dell reproduces the
same six.

## Record the witness

t has run on one Mac. A second is still worth keeping: note the macOS version
and architecture, which kernels you installed and from which assets, what
`run_par.py` printed for present and absent kernels, and the final agreement
line. Drop it in `t/` as `WITNESS-<date>-macos.md`. Claims here become true
the moment someone writes down that they happened.
