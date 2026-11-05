# Native TUP implementation status

The goal is [HEADLESS-GOAL.md](HEADLESS-GOAL.md). The live register is
[HEADLESS-HURDLES.json](HEADLESS-HURDLES.json). No native TUP build, installer,
physical installation or remote CPU/GPU qualification has passed yet.

The requested result is a continuously running native TUP host controlled from
the owner's MacBook. Disposable TUP guests install workload tools through an
in-guest package manager, keep running across remote disconnects, and discard
their writable state on explicit finish. Only selected results persist.

## Linux checkpoint: 2026-11-05

The integrated checkpoint at `f2ac0c1c` passes **135 tests, zero failures and
zero skips**, in 12.395 seconds on Linux. This includes the real GNU sync path
previously skipped on Windows. All 147 selected shell files pass syntax checks;
the offline book extraction exactly matches its committed bytes. The two
original upstream trailing spaces in generated Tcl/coreutils commands are
retained deliberately. [Verification](receipts/native-dev-20261105/verification.json)
links to the unchanged raw Linux test log. No hardware power-loss or native-boot
claim follows from these fixtures.

The separate maintained-book extraction inventories 143 pages, 640 command
blocks and 94 sources. Its command-bearing pages refuse execution until their
named native overrides are reviewed. The native13 CLI is still disabled. The
source checkpoint verifies 22 of 94 inputs against published HTTPS SHA256
metadata; unresolved sources and advisory dispositions prevent production
export. The full block audit, authenticated source lock and actual core build
are the next gates.

The hardware check found wired Ethernet now linked at 1 Gbps. The vendor INF
identifies USB Wi-Fi as RTL8852CU; the selected 6.18.60 kernel source lacks its
USB driver. H21 retains the need for a maintained backport or newer kernel and
separate native Wi-Fi tests. Working Windows networking is not a TUP result.

The owner requires continued work through headless boot, remote access,
adversarial tests and sustained tests on this desktop. Disposable image tests
precede preparation of the connected Ventoy USB; live hardware qualification
still precedes Windows replacement. No physical storage has been changed.

## First implementation checkpoint: 2026-11-04

- Research baseline: `a403386720e9ee67789b5ee0b92e303a972c8a34`.
- Goal recorded at `753c96f8754e7b22971da0283c6a0efe2088c8d2`.
- Receipt-byte fix integrated at `0a94efb9`: 18 focused Python tests pass on
  Windows. Original-byte hashes, CRLF/non-ASCII copies, component manifests and
  missing-evidence refusal are covered. Live Linux/remote collection is not.
- Native target-root preparation and chapter 5-8 orchestration were integrated
  at `54bb1b27` and `9f1e9d10`; `2ec3f725` adds full stage postconditions and the
  driver's stronger host-tool requirements.
- Input-bound driver resume and atomic receipt/state transactions were
  integrated at `b44f7113`. Changed, legacy, failed or uncertain state refuses
  automatic replay. No old QEMU wrapper can authorize the new native path.
- Final integration run: **76 tests, 75 passed, 1 skipped**, in 168.885 seconds
  on Windows Python 3.13.17 with Git Bash. The skipped test needs real Linux
  filesystem durability; Windows driver fixtures use a test-only sync adapter.
  Bash syntax and whitespace checks pass. Evidence is in
  [verification.json](receipts/native-dev-20261104/verification.json) and
  [the sanitized test output](receipts/native-dev-20261104/integration-windows.txt).
  Actual Linux namespace/durability behavior, source authentication and a
  complete LFS build remain unverified.
- H53 records the new disposable-instance package-manager requirement. Nix is a
  candidate because upstream supports non-systemd Linux installation; it has
  not been installed or selected as a qualified TUP component.
- H54 records upstream retirement of the maintained SysV book. The working
  production choice is 13.1-systemd plus reviewed advisory updates; migration
  and qualification remain open. [The baseline note](native/BASELINE.md) records
  the extraction, source-verification, test-policy and service changes needed.
  The initial builder refuses this new book until that migration is complete.

## Build environment

The preparation machine is Windows 11 x86_64, with a 12-core/24-thread CPU and
about 15.16 GiB usable RAM. Git and a portable Python 3.13.17 runtime are
available. Python's archive matched its published SHA256 and its executable
has a valid Python Software Foundation signature.

WSL 3.0.3 was installed from the official Microsoft release after checking the
published SHA256 and Authenticode publisher. The authorized Windows reboot
completed. Ubuntu 24.04.5 LTS now runs an x86_64 Linux build environment on
ext4. Build tools and distribution security updates are installed; a dedicated
locked `lfs` account exists. A private mount/PID namespace probe passed.
Windows drive automount and executable interoperability are disabled in this
builder. These observations do not establish isolation from a hostile build.
The initial disposable-builder budget is 6 GiB RAM, 8 virtual CPUs, 4 GiB swap
and four compiler jobs. These are preparation limits, not final native-host
performance claims. Build files must live on a Linux filesystem, not DrvFs.

The first automatic attempt to execute the installer was rejected with only
"blocked by policy". After the owner explicitly instructed installation, the
verified local installer succeeded. No administrator credential was needed or
stored. No physical disk or USB has been formatted.

## Predictions and next checks

Before running Linux qualification, predict that all retained unit fixtures
pass on Linux without Windows compatibility shims; a single failure falsifies
that prediction. In particular, real file/directory durability operations must
be exercised on Linux. Windows fixtures cannot establish crash durability.

Linux architecture, memory/CPU/swap limits, ext4 storage and mount/PID namespace
creation have been checked. Complete source authentication, the maintained
book's execution audit, and its profile-specific host checks before starting
a real base build. A failed preflight must stop without a completion marker or
an altered physical device. Check physical host free space as well as the
virtual ext4 filesystem before admitting a build.

The first whole-build prediction and peak-resource limits must be recorded
after those gates are satisfied. No build-duration prediction is justified yet.

Sources: [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install),
[WSL settings](https://learn.microsoft.com/en-us/windows/wsl/wsl-config),
[LFS maintenance status](https://www.linuxfromscratch.org/lfs/download.html),
[Nix binary installation](https://nix.dev/manual/nix/stable/installation/installing-binary).
