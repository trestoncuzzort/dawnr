# Native TUP implementation status

The goal is [HEADLESS-GOAL.md](HEADLESS-GOAL.md). The live register is
[HEADLESS-HURDLES.json](HEADLESS-HURDLES.json). No native TUP build, installer,
physical installation or remote CPU/GPU qualification has passed yet.

The requested result is a continuously running native TUP host controlled from
the owner's MacBook. Disposable TUP guests install workload tools through an
in-guest package manager, keep running across remote disconnects, and discard
their writable state on explicit finish. Only selected results persist.

## First implementation checkpoint: 2026-11-04

- Research baseline: `a403386720e9ee67789b5ee0b92e303a972c8a34`.
- Goal recorded at `753c96f8754e7b22971da0283c6a0efe2088c8d2`.
- Receipt-byte fix integrated at `0a94efb9`: 18 focused Python tests pass on
  Windows. Original-byte hashes, CRLF/non-ASCII copies, component manifests and
  missing-evidence refusal are covered. Live Linux/remote collection is not.
- Driver state/receipt transactions and the native target-root entrypoint are
  separate implementation lanes. Their results must be integrated and tested
  together before any LFS build is approved.
- H53 records the new disposable-instance package-manager requirement. Nix is a
  candidate because upstream supports non-systemd Linux installation; it has
  not been installed or selected as a qualified TUP component.
- H54 records upstream retirement of the maintained SysV book. The historical
  12.4 book is not automatically a safe production baseline. Maintenance and
  override migration remain open.

## Build environment

The preparation machine is Windows 11 x86_64, with a 12-core/24-thread CPU and
about 15.16 GiB usable RAM. Git and a portable Python 3.13.17 runtime are
available. Python's archive matched its published SHA256 and its executable
has a valid Python Software Foundation signature.

WSL 3.0.3 was installed from the official Microsoft release after checking the
published SHA256 and Authenticode publisher. The installer returned zero. The
required Windows features were enabled without restarting. WSL still reports
that a Windows restart is required; no Linux distribution/build has run yet.
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

After the Windows restart, verify the installed WSL runtime and install a
disposable Ubuntu 24.04 build distribution if it is still absent. Confirm Linux
architecture, memory/CPU/swap limits, ext4 build storage, chroot/mount facilities
and the selected LFS host requirements. Complete source authentication and the
maintained-book decision before starting a real base build. A failed preflight
must stop without a completion marker or an altered physical device.

The first whole-build prediction and peak-resource limits must be recorded
after those gates are satisfied. No build-duration prediction is justified yet.

Sources: [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install),
[WSL settings](https://learn.microsoft.com/en-us/windows/wsl/wsl-config),
[LFS maintenance status](https://www.linuxfromscratch.org/lfs/download.html),
[Nix binary installation](https://nix.dev/manual/nix/stable/installation/installing-binary).
