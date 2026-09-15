# Run t on Linux

t itself is plain Python 3.12 with no dependencies; the kernels do the
proving. This page is written on the box the project has run on all along,
the Dell (the lab workstation), confirmed fresh on 2026-09-11: Ubuntu 24.04.4
LTS, x86_64, kernel 6.8.0-138-generic. It is a no-root install: the account
has no sudo (`apt install` is unavailable, not merely password-gated), so
all seven kernels live under `$HOME` and nothing here needs a package
manager.

The honest summary first: Linux gives you all seven kernels, same as macOS
and unlike native Windows, but getting there costs more manual work than
macOS's four-from-homebrew story, because there is no root and so no
system package manager to lean on. Every kernel here is a release tarball,
a language-specific installer (elan, opam), or an opam package, all
resolved into `$HOME`.

## The seven kernels, confirmed on this box today

Versions below are each kernel's own version command, run on this box on
2026-09-11 with `PATH` extended as `export
PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$PATH`
(needed for `cargo`/`rustc`, which `opam` and Rocq's build chain use, and
for the `opam`/`elan` shims themselves).

| Kernel | Version (measured) | Path (measured) |
|---|---|---|
| Dafny | `4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2` | `~/.local/dafny/dafny` |
| Verus | `0.2026.08.30.b432e82`, toolchain 1.97.1-x86_64-unknown-linux-gnu | `~/.local/verus/verus-x86-linux/verus` |
| GNATprove | FSF 16.1.0, Why3 1.8.2+git, bundled Alt-Ergo 2.6.1 / cvc5 1.3.2 / Z3 4.15.4 | `~/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin/gnatprove` |
| Lean | 4.33.1, x86_64-unknown-linux-gnu, commit 819816b2e0a3 | `~/.elan/bin/lean` (elan default toolchain, `~/.elan/settings.toml`) |
| Rocq | The Rocq Prover, version 9.2 (OCaml 4.14.4) | `~/.opam/default/bin/coqc` (also `rocq`) |
| Frama-C | 33.0 (Arsenic) | `~/.opam/default/bin/frama-c` |
| F\* | 2026.08.30, OCaml 5.3.0, commit 2b82aefeff37 | `~/.local/fstar/fstar/bin/fstar.exe` |

Two more things confirmed inside the `default` opam switch alongside Rocq
and Frama-C, because the task asked for them: `alt-ergo-free` 2.4.3
(`alt-ergo --version` reports `2.4.3-free`) is Frama-C's WP prover, and
`opam list` shows `rocq-stdlib.9.2.0` pinned, not the plain registry
package (below). `opam --version` on this box is 2.5.2; the switch's
compiler is `ocaml-base-compiler.4.14.4`.

Commands run to produce the table above: `~/.local/dafny/dafny --version`,
`~/.local/verus/verus-x86-linux/verus --version`,
`~/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin/gnatprove
--version`, `~/.elan/bin/lean --version`, `coqc -v` (and `rocq --version`,
same answer), `frama-c -version`, `~/.local/fstar/fstar/bin/fstar.exe
--version`, `alt-ergo --version`, `opam --version`, `opam list` filtered to
rocq/coq-core/frama-c/alt-ergo.

## How each kernel got under `$HOME`

Four are self-contained release tarballs unpacked under `~/.local/`; the
byte-for-byte archive and download URL for each is not present on this box
today (no `.zip`/`.tar.gz` or `.sha256` sits next to any of the four
unpacked trees, unlike the Mac's tarball installs), so the exact asset name
for Dafny and GNATprove on Linux is **recorded, not re-run**: the Windows
page's table already names the pattern (`dafny-4.11.0-x64-windows-2022.zip`
etc. for Windows; the Linux release listings on the same GitHub repos carry
the `-linux` siblings, e.g. GNATprove's own unpacked directory name here,
`gnatprove-x86_64-linux-16.1.0-1`, is exactly its release asset's base
name, same for Verus's `verus-x86-linux` and F\*'s
`fstar-v2026.08.30-Linux-x86_64` family). What is re-derivable from the box
is only the destination layout:

| Kernel | Unpacked to |
|---|---|
| Dafny 4.11.0 | `~/.local/dafny/` (release zip from github.com/dafny-lang/dafny, tag v4.11.0, **recorded, not re-run**) |
| Verus 0.2026.08.30.b432e82 | `~/.local/verus/verus-x86-linux/` (release zip from github.com/verus-lang/verus, **recorded, not re-run**; needs `~/.cargo/bin` on `PATH` because Verus's own binary shells out to `rustc` from the toolchain rustup installed) |
| GNATprove FSF 16.1.0 | `~/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/` (release tarball from github.com/alire-project/GNAT-FSF-builds, tag gnatprove-16.1.0-1, **recorded, not re-run**) |
| F\* 2026.08.30 | `~/.local/fstar/fstar/` (release tarball from github.com/FStarLang/FStar, tag v2026.08.30, **recorded, not re-run**) |

Two come from language installers that put everything under `$HOME` by
design:

* **Lean 4.33.1** via elan: `~/.elan/settings.toml` on this box reads
  `default_toolchain = "leanprover/lean4:v4.33.1"`, i.e. `elan default
  leanprover/lean4:v4.33.1` was run (elan's own installer script is
  `curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh
  -sSf | sh`, **recorded, not re-run**: elan is already present here).
* **Rust toolchain** via rustup, needed by Verus and by opam's own OCaml
  build chain: `cargo 1.97.1`, `rustup 1.29.0`, active `rustc 1.97.1`, all
  on `~/.cargo/bin`. rustup's own no-root installer is `rustup-init` from
  rustup.rs, **recorded, not re-run**.

The last two, Rocq and Frama-C, share one opam switch, confirmed by
`opam switch list` reporting a single switch named `default`
(`ocaml-base-compiler.4.14.4,ocaml-options-vanilla.1`), and `opam list`
inside it showing all four packages this task asked about together:
`rocq-core.9.2.0`, `rocq-runtime.9.2.0`, `coq-core.9.2.0` (the
"Compatibility binaries for Coq after the Rocq renaming", which is what
puts `coqc` on the switch's `bin/` next to `rocq`), `frama-c.33.0`, and
`alt-ergo-free.2.4.3`. opam itself installs no-root into `~/.opam` by
design (`bash -c "$(curl -fsSL
https://raw.githubusercontent.com/ocaml/opam/master/install.sh)"`, then
`opam init`, **recorded, not re-run**: opam 2.5.2 is already present).

`rocq-stdlib` is not the plain opam-registry package: `opam show
rocq-stdlib` on this box reports `pin
https://github.com/rocq-prover/stdlib/releases/download/V9.2.0/stdlib-9.2.0.tar.gz`,
i.e. it was installed with

```bash
opam pin add rocq-stdlib https://github.com/rocq-prover/stdlib/releases/download/V9.2.0/stdlib-9.2.0.tar.gz
```

That pin command is confirmed live in `opam show`'s output today; the
session that first ran it is **recorded, not re-run**. The rest of the
switch (`opam install frama-c alt-ergo-free rocq-core coq-core`, the
ordinary registry route) is likewise **recorded, not re-run**: no opam log
survives on this box naming the exact install sequence, only the resulting
switch contents, which the table above gives in full.

## Pointing t at the binaries: nothing to do here

Discovery tries, in order: a `T_*` environment variable, then `PATH`, then
glob patterns under `$HOME`. The names, from `verifiers/discover.py`:
`T_DAFNY`, `T_VERUS_BIN`, `T_GNATPROVE`, `T_FRAMAC`, `T_LEAN_BIN`,
`T_COQC`, `T_FSTAR`. Each adapter's own glob, read from
`t/verifiers/*.py`:

```
dafny     .local/dafny/dafny
verus     .local/verus/**/verus
gnatprove .local/gnatprove/**/bin/gnatprove
framac    .opam/*/bin/frama-c
rocq      .opam/*/bin/coqc
lean      .elan/bin/lean
fstar     .local/fstar/fstar/bin/fstar.exe (also .local/fstar/**/bin/fstar.exe)
```

Six of these seven globs matched on this box with no `T_*` variable set,
returning the paths in the version table above. Dafny is the exception:
`find()` tries `PATH` before the glob, and this box has had a root-owned
system copy at `/opt/dafny-4.11.0` (symlinked as `/usr/local/bin/dafny`,
dated 2026-09-03) since after the no-root install, so `find()` returns
that one; both copies print the same `4.11.0+fcb2042d` and the table's
`~/.local/dafny/dafny` is the no-root path this page installs (checked
2026-09-11 by an independent re-run of `verifiers.dafny.DAFNY`). Frama-C and Rocq both resolve
through the `.opam/*/bin/` glob into the single `default` switch, so having
Rocq, Frama-C, and Alt-Ergo share one switch costs nothing extra at
discovery time; they were also reachable on `PATH` once
`$HOME/.opam/default/bin` was added to it, ahead of the glob tier.

**Do not check for a kernel with `command -v`** before extending `PATH`:
`opam`'s and `elan`'s binaries, and every tarball install, sit outside a
login shell's default `PATH` until `eval $(opam env)` or an explicit export
runs. Ask the adapter instead:

```bash
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$PATH
cd t
python3 -c "from verifiers.verus import VERUS, _VERUS_WHY; print(VERUS or _VERUS_WHY)"
```

## Python: 3.12, and it is already the system interpreter here

`python3 --version` on this box is `Python 3.12.3` at `/usr/bin/python3`,
which already satisfies the drivers' 3.12 requirement with no separate
install and no venv: everything in `t/` is standard library. (The
project's separate pinned 3.12.10 interpreter, used elsewhere on this
machine for a dataset gate, is a stricter pin than t itself needs; t's own
suite has never required more than 3.12.)

## What running it looks like

```bash
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$PATH
cd t
python3 run_par.py --jobs 8 --tasks tasks --out /tmp/t-linux-walk --table /tmp/t-linux-walk.md
```

`run_par.py` refuses to write a table from fewer than two kernels
(`T_MIN_KERNELS`), names every absent one and where it looked, and exits
nonzero on a disagreement rather than calling it agreement.

## The walk-through, run on this box on 2026-09-11

Copied `t/tasks/abs.json`, `t/tasks/gcd.json`, `t/tasks/reverse.json` into
a scratch directory and ran, with `PATH` set as above:

```
python3 t/run_par.py --jobs 8 --tasks <dir with abs.json, gcd.json, reverse.json> \
    --out <scratch>/linux-install-walk --table <scratch>/linux-install-walk.md
```

Exit code: `0`. Console output, one line per task/kernel cell plus the
final verdict:

```
  abs x verus [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  gcd x verus [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  reverse x verus [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])
  abs x dafny [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  gcd x dafny [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  reverse x dafny [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])
  abs x lean [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  abs x framac [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  gcd x lean [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  abs x spark [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  reverse x lean [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])
  abs x fstar [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  abs x rocq [collapse-if]: real=verified twin=refuted   (twin witness: x=1 -> real 1, twin -1)
  gcd x fstar [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  reverse x fstar [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])
  gcd x framac [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  gcd x spark [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  gcd x rocq [collapse-if]: real=verified twin=refuted   (twin witness: a=1, b=0 -> real 1, twin 0)
  reverse x rocq [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])
  reverse x framac [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])
  reverse x spark [invariant-drop#1]: real=verified twin=refuted   (twin witness: exit at s=[], i=0, r=[0])

7 kernels, 3 tasks: FULL AGREEMENT
```

The table it wrote, `linux-install-walk.md`:

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| gcd | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar).
Sole-blocker table: every kernel 0 sole-blocked and 0 co-blocked tasks, 0 of
0 tasks blocked in six kernels. Backends line matches the version table
above exactly (dafny 4.11.0+fcb2042d, verus 0.2026.08.30.b432e82, spark
FSF 16.1.0 / Why3 1.8.2+git, framac 33.0 (Arsenic) / alt-ergo 2.4.3-free,
lean 4.33.1, rocq 9.2, fstar 2026.08.30 / OCaml 5.3.0 /
commit 2b82aefeff37f78509c876844954b07fcb8813ff).

## What is still open

**2026-09-11**: this page was written and its walk-through run entirely on
the Dell (the lab workstation), the same machine that has run t all along; the
bar's "followed from a fresh machine by a second person" is **open by
name**, no second person and no second Linux machine has followed this
page yet, unlike the Windows page (confirmed 2026-09-02 on a separate
Windows 11 machine) and the macOS page (confirmed 2026-09-06 on a separate
Mac). The four tarball installs' exact download URLs and the opam
package-install command line (as opposed to the pin, which `opam show`
still states) are recorded above as "recorded, not re-run" because no
install log or archived asset survives on this box to requote verbatim;
a fresh run of this page on a second Linux box would pin those down for
real and would satisfy the bar's walk-through requirement. Record a second
Linux install as `t/WITNESS-<date>-linux.md`, following the shape of
`WITNESS-2026-09-06-macos.md`.
