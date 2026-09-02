# Run t on a Windows PC

t itself is plain Python 3.12 with no dependencies; the kernels do the
proving. Five of the seven have real Windows builds, verified against their
release listings on 2026-09-02 (the asset names below are copied from those
listings, not guessed). t has now run on a real Windows machine: 2026-09-02,
Windows 11 Pro, Python 3.12.10, Dafny 4.11.0 + Lean 4.33.1 + F* 2026.08.30
installed user-local with no PATH edits and no `T_*` variables, found by the
home-directory glob; `run_all.py` 3 kernels x 11 tasks FULL AGREEMENT in
99 s, `run_par.py` the same in 10 s under the spawn start method, 33/33
cells `verified / refuted`. The witness file is held by the person who ran
it; this page records what it established and what it broke (below).

The honest summary first: **WSL2 gives you all seven kernels** by following
the Ubuntu instructions verbatim inside an Ubuntu WSL2 distribution.
**Native Windows gives you five**, which is plenty: `run_all.py` refuses to
conclude from fewer than two kernels, records every absent one with the
exact places it looked, and treats a partial matrix as a smaller real
measurement, not a failure. Five kernels agreeing and refuting is
legitimate cross-kernel verification.

## The five native kernels, with their verified release assets

| Kernel | Asset (from the release page) | Where |
|---|---|---|
| Dafny 4.11.0 | `dafny-4.11.0-x64-windows-2022.zip` | github.com/dafny-lang/dafny, tag v4.11.0 |
| Verus 0.2026.08.30 | `verus-0.2026.08.30.b432e82-x86-win.zip` | github.com/verus-lang/verus (needs rustup: rustup.rs ships rustup-init.exe) |
| F* 2026.08.30 | `fstar-v2026.08.30-Windows_NT-x86_64.zip` | github.com/FStarLang/FStar, tag v2026.08.30 |
| GNATprove FSF 16.1.0 | `gnatprove-x86_64-windows64-16.1.0-1.tar.gz` | github.com/alire-project/GNAT-FSF-builds, tag gnatprove-16.1.0-1 |
| Lean 4.33.1 | `elan-x86_64-pc-windows-msvc.zip`, then `elan default leanprover/lean4:v4.33.1` | github.com/leanprover/elan |

The two that stay on WSL2: **Rocq** and **Frama-C** install through opam,
which is Unix-oriented. Rocq has a native Windows route via the Coq
Platform installer plus `T_COQC` pointing at its `coqc.exe`, but that is
untried here; Frama-C's own documentation points Windows users at WSL2.

## Pointing t at the binaries

Discovery tries, in order: a `T_*` environment variable, then `PATH`, then
glob patterns under your home directory (`.exe` variants are tried
automatically). On Windows the reliable route is the environment variable.
The names, from `verifiers/discover.py`: `T_DAFNY`, `T_VERUS_BIN`,
`T_GNATPROVE`, `T_FRAMAC`, `T_LEAN_BIN`, `T_COQC`, `T_FSTAR`.

PowerShell example:

```powershell
$env:T_DAFNY   = "C:\tools\dafny\dafny.exe"
$env:T_FSTAR   = "C:\tools\fstar\bin\fstar.exe"
cd path\to\tup\t
py -3.12 run_all.py      # not `python`: a stock box resolves that to 3.11
```

`py -3.12`, not `python` or `py -3`: on a box with more than one Python the
bare names picked 3.11 (measured), and the drivers are 3.12 code. (The one
syntax that actually failed on 3.11, an f-string with a nested `"` , is gone
since 2026-09-02, but nothing else on 3.11 is tested and the receipt says
3.12.) `run_all.py` prints one line per absent kernel saying exactly where it
looked. Two or more present kernels and the suite runs; fewer and it
refuses, by design, because agreement measured on nothing is one opinion,
or none.

## What was made portable, and how it was tested without a Windows box

The parallel drivers used to hard-select the `fork` start method, which
does not exist on Windows; they now select fork where it exists and spawn
elsewhere (`verifiers.mp_context`). The live-run guard used to scan
`/proc`, which also does not exist on Windows; a lock file in `out/`
provides mutual exclusion on every platform. The `/proc` scan was kept as
an extra Linux check until 2026-09-02, when it refused against its own
launcher (`timeout 600 python3 run_par.py` carries the script name in the
wrapper's argv) inside a tup guest; the lock already answered the question,
so the scan is gone. The spawn branch was exercised on Linux by forcing it
(`T_MP_START=spawn`) and then for real on Windows (10 s, full agreement).
The Windows-specific liveness check inside the lock was measured on that
box the same day: a second live process refuses naming the holder's pid, a
dead holder (pid 4000000) is taken over, an unparseable holder refuses
(fails closed), release removes the file, and `os.kill` is never reached.

Two more things that Windows run found, both fixed the same day. A run
with too few kernels used to write the (empty) table *before* refusing, so
a fresh clone's first `run_all.py` replaced the committed `AGREEMENT.md`
with an empty one; the refusal now comes first and the witness is a
zero-kernel run after which the file's sha256 is unchanged. And
`Path.write_text` defaulted to `os.linesep`, so the lowered sources were
CRLF on Windows and their hashes, the verdict basis, differed from every
other platform's for the same text (`abs.dfy` `9147e4af…` vs `9fe1e7e8…`,
equal after CRLF->LF); every write site now passes `newline="\n"`, and
`.gitattributes` pins `t/` to LF on checkout so `autocrlf=true` cannot
re-introduce it through the committed fixtures.

## Record the witness

t has run on one Windows machine. A second is still worth keeping:
note the Windows version, which kernels you installed and from which
assets, what `run_all.py` printed for present and absent kernels, and the
final agreement line. Drop it in `t/` as
`WITNESS-windows-<date>.md`. Claims here become true the moment someone
writes down that they happened.
