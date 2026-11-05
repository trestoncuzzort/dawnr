# Native TUP implementation status

The goal is [HEADLESS-GOAL.md](HEADLESS-GOAL.md). The live register is
[HEADLESS-HURDLES.json](HEADLESS-HURDLES.json). No native TUP build, installer,
physical installation or remote CPU/GPU qualification has passed yet.

The requested result is a continuously running native TUP host controlled from
the owner's MacBook. Disposable TUP guests install workload tools through an
in-guest package manager, keep running across remote disconnects, and discard
their writable state on explicit finish. Only selected results persist.

## Resumed: 2026-11-05

The owner resumed the work the same day. Nothing below is a completed core,
a boot or a login; it records what was fixed, what a rehearsal measured and
what is still running.

**Run 001's blocker is fixed and demonstrated.** In an isolated copy of the
failed root, inside its chroot with the target loader, the bare `./python`
call reproduced exit 127 and the replacement through CPython's own
`$(RUNSHARED) $(PYTHON_FOR_BUILD)` variables passed both backport
regressions while mapping the build tree's `libpython`. The original
workspace hashed identically before and after the copy.

**A rehearsal replaces rebuild-per-failure.** The driver rightly refuses to
resume a failed page, so every later defect would have cost a full rebuild.
Instead a copy of failed run 001 is being continued page by page with the
unchanged driver, a fresh ledger and required suites judged but not fatal.
It is explicitly non-authoritative: nothing from it is validated, exported
or counted as a pass. A read-only review of every never-executed chapter 8
page ran beside it, with each serious finding checked independently. Together
they found, before any authoritative rebuild:

- The 4 GiB build budget cannot run glibc's suite. Two tests build strings
  above 2 GiB on purpose and peaked at 4.74 GiB together in an isolated
  measurement; the first rehearsal attempt was killed by the cgroup's
  group OOM policy at 4 GiB plus 2 GiB swap. With 6 GiB both pass.
- The builder's wall clock was being stepped about every 32 seconds: an NTP
  client inside the builder and the hypervisor's own time synchronization
  disagreed by about 0.67 s. Two glibc timing tests failed in one attempt
  because of it, and timestamp-driven builds were exposed. The in-guest
  client is now stopped for build windows and the run helper refuses to
  start while it is active.
- An unattended package upgrade was scheduled inside the build window and
  would have invalidated the inventoried host tools; those timers are stopped.
- The glibc timeout diagnostic could not survive a clean suite (the page's
  ERR trap ignores `set +e`); fixed, with a test that executes the audited
  block under the real prologue.
- The zero-tolerance suite gate meets failures that the LFS book documents
  for this exact toolchain (glibc `io/tst-lchmod` in any chroot, a gprofng
  test in binutils, a list in GCC). The gate now accepts only reviewed, exact
  result lines with a pass floor for those three suites
  ([policy](native/profiles/lfs-13.1-systemd/suite-exceptions/README.md));
  glibc's list holds the one line actually observed. Lists for binutils and
  GCC do not exist until the rehearsal has observed those suites.
- tar's capability test compares against an obsolete `getcap` format and
  Python's suite enables network tests without a resolver; both are corrected
  in their audited blocks.

In the rehearsal so far chapter 7 completed (the temporary Python regression
recorded PASS) and chapter 8 is in progress: glibc built, ran 6,823 to 6,824
passing tests across attempts and installed. Its recorded verdict in the
last attempt is still *failed*, correctly, because of the two clock-induced
failures; the next authoritative run must show them passing.

**Integrated on main and tested on Linux (334 tests, zero skips):** the layer
runner that exports a validated core and builds the remote and boot chapters
in it; pages for libmnl, libnftnl, nftables, OpenSSH, sudo, the device-mapper
part of LVM2, the kernel and the selected firmware; authenticated sudo
1.9.17p2; and a kernel configuration extended for KVM guests, device
assignment, sensors, watchdog and rescue filesystems, re-qualified by a
committed script. All seven layer archives and sudo were re-authenticated by
the real verifier in the builder. None of these pages has run in a target
root yet.

Still in progress: owner enrollment at boot with the system configuration
chapter, the Ventoy live-boot adapter, and an external-VM test that performs
a real SSH login. The next authoritative core build starts when the rehearsal
has passed every chapter 8 page.

## Paused for Claude handoff: 2026-11-05 (historical)

The owner requested a pause and a handoff to Claude; the automatic goal was
cleared. See [HANDOFF-CLAUDE.md](HANDOFF-CLAUDE.md) for the current state and
the exact next work. All worker lanes stopped; no task QEMU process or attached
loop device remained at the pause audit.

The first real core build **failed** during temporary Python's added regression
check after chapters 5 and 6 passed. The bare `./python` invocation could not
locate its shared libpython; upstream's Makefile supplies RUNSHARED for this.
The proposed fix is unimplemented. The original workspace, failed intent and
logs are preserved. No replacement build has started. The
[failure receipt](receipts/native-dev-20261105/core-001-failure.json) and
[original stage log](receipts/native-dev-20261105/core-001-ch07-failure.log)
retain the failure and final resource observations.

Integrated main d35a0ff3 passed **290 Linux tests, zero skips** before the pause:
[receipt](receipts/native-dev-20261105/verification-d35a0ff3.json),
[raw log](receipts/native-dev-20261105/integration-d35a0ff3-linux.txt).
The disposable regular-file installer and isolated firewall probes passed their
declared tests. A host-only Ventoy UEFI smoke reached its GRUB marker but timed
out during halt; its stored verdict is FAILED. None is a complete TUP boot or
remote-login result. Unfinished remote-target and runtime-test code remains in
worker worktrees, with a private handoff snapshot.

## Historical core build launch: 2026-11-05

The following launch checkpoint predates the failure above.


The first complete native-profile LFS build is running from frozen commit
`cbabbd393a6d6d1470329d6b64defeafaf0f0392`. Preflight and fresh-root preparation
passed, and the first Binutils stage completed. The build uses four compiler
jobs under systemd limits of 4 GiB memory, 2 GiB swap and four CPUs. This is an
active build, not a completed core or boot result. Its private workspace retains
original package/stage logs, receipts and aggregate resource observations.

That exact snapshot passed **256 integrated Linux tests, zero skips**;
[verification](receipts/native-dev-20261105/verification-cbabbd39.json) binds
[the original log](receipts/native-dev-20261105/integration-cbabbd39-linux.txt).
The [core progress snapshot](receipts/native-dev-20261105/core-001-progress.json)
records the completed pages without claiming whole-build success. The latest
remote-policy checkpoint passes [258 tests](receipts/native-dev-20261105/verification-73a7e1dd.json)
and adds complete effective-configuration checks and
stops the SSH session cgroup when the access service stops; durable workloads
must use separate managed services. Actual remote login remains untested.

The [source closure](sources/README.md) accepts all 94 selected inputs: 83
authenticated and 11 exact, separately counted provenance exceptions. The
build-only lock binds 102 advisory dispositions, the two tested Python
backports, and open Expat release gate H55. Its SHA256 is
`8c46c28a74f760ddf62df17f34327ac24dde7b465ab7c1bf3b9dbc7551522a05`.
The [native profile](native/profiles/lfs-13.1-systemd/README.md) now enables the
audited 124-page, 580-block chapter 5-8 execution plan and retained package tests.

Authenticated dracut 112, GRUB 2.14 EFI and SquashFS 4.7.5 host tools have
[actual build/packaging evidence](boot/HOST-TOOLS.md). Metadata roundtrip and
an EFI smoke ISO inspection passed. That smoke image contains no TUP kernel or
root and has not booted. The real TUP kernel, live ISO, Ventoy and installed boot
remain required gates. The installer is reusing systemd-repart; disposable
testing exposed that `--empty=create` overrides dry-run and that split output
is independent of dry-run. Physical targets remain inaccessible to the current
fixture adapter.

The requested [fetch-before-fic skill](skills/fetch-before-fic/SKILL.md) is
validated, installed in the preparation machine's user skill directory and
retained here for transfer to the next development machine. New work must
research and reuse existing implementations before adding custom code.

## Earlier Linux checkpoint: 2026-11-05

The integrated checkpoint at `f2ac0c1c` passes **135 tests, zero failures and
zero skips**, in 12.395 seconds on Linux. This includes the real GNU sync path
previously skipped on Windows. All 147 selected shell files pass syntax checks;
the offline book extraction exactly matches its committed bytes. The two
original upstream trailing spaces in generated Tcl/coreutils commands are
retained deliberately. [Verification](receipts/native-dev-20261105/verification.json)
links to the unchanged raw Linux test log. No hardware power-loss or native-boot
claim follows from these fixtures.

At that checkpoint, the separate maintained-book extraction inventories 143 pages, 640 command
blocks and 94 sources. Its command-bearing pages refuse execution until their
named native overrides are reviewed. The native13 CLI was still disabled. The
source checkpoint verifies 22 of 94 inputs against published HTTPS SHA256
metadata; unresolved sources and advisory dispositions prevent production
export. The full block audit, authenticated source lock and actual core build
were the next gates; the current build status above supersedes that checkpoint.

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
