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

## A second Mac, 2026-09-16: M3 Max, 14 cores, 36 GB, Xcode 27

    macOS 26.6.2 build 25G83, Apple M3 Max (10 performance + 4 efficiency
    cores), 36 GB, Xcode 27.0 (27A266a), Apple clang 21.0.0
    Python 3.12.10 via uv at ~/.local/bin/python3.12 for the drivers

The table above still holds, with four deviations, each measured before it
was written down. The witness is `WITNESS-2026-09-16-macos-m3max.md`.

| Kernel | Resolved at | What differed from the 2026-09-06 route |
|---|---|---|
| Dafny 4.11.0 | `~/.local/dafny/dafny` | `brew install dafny` puts no z3 in its Cellar and takes whatever `z3` is on PATH (5.1.0 that day), while Dafny 4.11.0 expects its own 4.12.1. The release zip `dafny-4.11.0-arm64-macos-13.zip` (tag v4.11.0) unpacked to `~/.local/dafny` bundles z3 4.12.1 and reports the Dell's exact string, `4.11.0+fcb2042d6d04...`. The brew copy was uninstalled so PATH does not shadow the glob. |
| Verus 0.2026.08.30.b432e82 | `~/.local/verus/verus-arm64-macos/verus` | The zip alone prints `verus needs a rustup installation`. rustup from sh.rustup.rs with `--no-modify-path --default-toolchain none`, then `rustup toolchain install 1.97.1-aarch64-apple-darwin` (the version the launcher names), and `~/.cargo/bin` on PATH: the launcher looks for `rustup` there and fails without it, so `. "$HOME/.cargo/env"` went into `~/.zshenv`. |
| GNATprove FSF 16.1.0 | `~/.local/gnatprove/gnatprove-aarch64-darwin-16.1.0-1/bin/gnatprove` | none; the `.sha256` beside the tarball matched. |
| Frama-C 33.0, alt-ergo 2.4.3-free, why3 1.8.2 | `~/.opam/default/bin/frama-c` | see below: OCaml compiled by this Xcode crashes, so the switch runs on Homebrew's OCaml bottle. |
| Lean 4.33.1 | `/opt/homebrew/bin/lean` | `brew install elan-init` puts elan's proxies on PATH, so discovery's second tier catches `lean` before the `.elan/bin/lean` glob; both run the same toolchain (`elan-init -y --no-modify-path --default-toolchain leanprover/lean4:v4.33.1`). |
| Rocq 9.2 | `/opt/homebrew/bin/coqc` | none. |
| F* 2026.08.30 | `~/.local/fstar/fstar/bin/fstar.exe` | none. |

**OCaml built by opam under Xcode 27 segfaults in `Unix.pipe`.** With
`opam init --compiler=ocaml-base-compiler.4.14.4` (the Dell's compiler) the
compiler builds and `print_endline` works, but a three-line program calling
`Unix.pipe ()` dies with `EXC_BAD_ACCESS, KERN_INVALID_ADDRESS at 0x0` inside
`unix_pipe`, native and bytecode alike, so `ocamlbuild` dies the first time
it spawns a command and `topkg` (needed by `bos`, needed by `yaml`, needed by
`frama-c`) never builds. `ocaml-base-compiler.5.3.0` built here fails the same
test. Homebrew's `ocaml` 5.5.0 bottle (built elsewhere) passes it, and so does
the F* release (OCaml 5.3.0, built on the F* CI). The route that worked:

```bash
brew install opam ocaml autoconf automake graphviz pkgconf zlib
opam init -y --no-setup --bare
opam switch create default --packages=ocaml-system      # brew's 5.5.0
export LIBRARY_PATH=/opt/homebrew/lib CPATH=/opt/homebrew/include   # zarith's -lgmp
export CAML_LD_LIBRARY_PATH=$HOME/.opam/default/lib/stublibs        # why3.byte's dllcamlzip
export PKG_CONFIG_PATH=/opt/homebrew/opt/zlib/lib/pkgconfig
opam install -y --confirm-level=unsafe-yes frama-c.33.0 alt-ergo-free.2.4.3 why3.1.8.2
```

The three exports are what `opam env` does not do for a system-compiler
switch on this box: without `LIBRARY_PATH` alt-ergo's link ends in
`___gmpz_* ... symbol(s) not found for architecture arm64`, and without
`CAML_LD_LIBRARY_PATH` why3 stops at `dllcamlzip.so: No such file or
directory`. `frama-c -version` reads `33.0 (Arsenic)` and `alt-ergo
--version` reads `2.4.3-free`, the pins. `~/.opam/default/bin` is on PATH from
`~/.zshenv` so WP finds `alt-ergo`, the same line `reproduce.sh` exports.
Whether the crash is Xcode 27's clang or the macOS 26 SDK is not known; what
is known is that two locally compiled OCaml versions fail the same
three-line test and two prebuilt ones pass it.

**why3 does not recognise `2.4.3-free`, and WP then runs the wrong driver.**
why3 1.8.2's `provers-detection-data.conf` has an entry for Alt-Ergo
2.4.0 to 2.4.3 with the native `alt_ergo` driver, but its `version_regexp`
is `^\([0-9.]+\)$` and `alt-ergo --version` prints `2.4.3-free`, so
`why3 config detect` reports `Prover Alt-Ergo version  is not recognized`
and WP, with no `~/.why3.conf`, lists `Prover Alt-Ergo [Alt-Ergo:]
(alt-ergo) (counter-examples)`: an empty version and the SMT-LIB driver
meant for 2.5 and later. Most goals still prove that way. The ones that do
not are every goal that uses a polymorphic `define-fun` (`eqmem`, `memcpy`:
the seq-returning tasks `filter_pos`, `reverse`, `swap`, `tail`), where
2.4.3's psmt2 frontend answers `Syntax error` at the body of the definition
and WP records the goal as `Failed`, which `verifiers/framac.py` reads, by
its doctrine, as `tool_error / tool_error`. The first matrix on this Mac read
exactly those four cells that way (run 1 in the witness). The fix is to tell
why3 the version yourself:

```bash
why3 config detect          # writes ~/.why3.conf with nothing for alt-ergo
cat >> ~/.why3.conf <<'CONF'

[prover]
command = "/Users/<you>/.opam/default/bin/alt-ergo --timelimit %.t %f"
command_steps = "/Users/<you>/.opam/default/bin/alt-ergo --steps-bound=%S %f"
driver = "alt_ergo"
editor = "altgr-ergo"
in_place = false
interactive = false
name = "Alt-Ergo"
shortcut = "alt-ergo"
version = "2.4.3"
CONF
frama-c -wp-list-provers    # now: Prover Alt-Ergo 2.4.3 [Alt-Ergo:2.4.3] (alt-ergo)
```

After that `filter_pos` reads verified with the twin refuted through the
adapter. Whether the Dell and the 2026-09-06 Mac carry such a file, or an
alt-ergo whose `--version` prints a bare `2.4.3`, is not recorded; on a fresh
install of `alt-ergo-free.2.4.3` from today's opam repository this step is
needed, and `-wp-list-provers` is the one-line check that tells you which
driver WP is about to use.

**The lab app.** `t/lab.py` needs a Python whose Tk initialises. uv's 3.12.10
ships tkinter and Tcl/Tk 8.6 but `Tk()` dies with `Can't find a usable
init.tcl` unless `TCL_LIBRARY` and `TK_LIBRARY` point into its own `lib/`.
Homebrew's `python@3.12` (3.12.14) with `python-tk@3.12` (Tk 9.0) needs
nothing, registers as the app "Python" on the desktop, and is what
`internal/MACHINES.md` describes, so the venv is built on it:

```bash
brew install python@3.12 python-tk@3.12
/opt/homebrew/bin/python3.12 -m venv ~/.venv-t && ~/.venv-t/bin/pip install torch
PATH=$HOME/.opam/default/bin:$HOME/.cargo/bin:$PATH ~/.venv-t/bin/python t/lab.py
```

torch 2.14.0 on that venv reports Metal (`torch.backends.mps.is_available()`
is True). `lab.py`'s `KERNEL_PATH` names the Linux Verus and GNATprove
directories, which do not exist here and do no harm: both kernels are found
by the adapters' globs, and the two PATH entries that matter on this Mac
(`.cargo/bin` for rustup, `.opam/default/bin` for alt-ergo) are in the list.
With the matrix running under `T_WATCH=~/.cache/t-watch/events.jsonl` (the
app's default), the Live checks tab showed each cell as it started and ended.

**Two more lines for the loop on a Mac.** `locallm/model.py` now takes the
plain attention path when training with dropout on MPS, because torch 2.14's
fused kernel there raises `scaled_dot_product_attention for MPS does not
support dropout` (same math, no fusion; the first `t/loop_filter.py` round
died on it). And `t/loop_filter.py` resolves `--work` to an absolute path,
because it runs `locallm/train.py` from `locallm/` and a relative work
directory was read from the wrong place. With both, round 0 trains on the
M3 Max's GPU (the bench: 26.6 ms per step on the default preset, 2,000 steps
in 53 s).

Two things that were not the machine: the network lost DNS for a few minutes
mid-install (`curl: (6) Could not resolve host` for github.com, opam.ocaml.org,
releases.lean-lang.org), which aborted two opam runs and one elan download,
and every one of them succeeded on a plain retry; and `git clone` without
`git-lfs` installed stops half way through checkout (`git-lfs: command not
found`, the tree missing `t/` and `tup/`), so `brew install git-lfs` comes
first.
