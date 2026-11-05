# Native LFS core builder

This entrypoint builds an explicit directory-backed x86_64 LFS core on a
trusted disposable Linux builder. It accepts no disk device, partitions
nothing, and has no QEMU or Windows dependency. A completed chapter 8 is still
not a bootable, installable or remotely accessible TUP release. The remaining
native gates stay in [HEADLESS-GOAL.md](../HEADLESS-GOAL.md).

`--profile lfs-13.1-systemd` selects the reviewed maintained core described in
[the profile audit](profiles/lfs-13.1-systemd/README.md). It uses every selected
chapter 5-8 page through an explicit hash-bound block plan. The historical
`lfs-12.4-sysv` profile/book remains available for historical reproduction; it
is not approved for production. A profile cannot silently select another
book/init version or inherit the old shared overrides.

## Host and resources

Use a dedicated Linux x86_64 builder with ext4 storage, root orchestration, and
an existing unprivileged `lfs` account for chapters 5 and 6. The workspace and
all its ancestors must be root-owned and not writable by group/other users;
`/srv/tup-build/run-001` is a suitable layout. The workspace must initially be
empty and traversable by the build user. Source checkout, source cache and
workspace must be disjoint. Symlinks in input/control paths are refused.

The host needs Python 3.10+, Bash 4.4+, GNU coreutils 8.24+, the selected book's
build tools and working mount/PID namespaces. The native13 host kernel minimum
is 5.10, with GCC through 16.2.0 and binutils through 2.47. Early chroot needs
only Bash and temporary coreutils; it does not require Python or flock. Host
probes use `/usr/sbin:/usr/bin:/sbin:/bin` and the C locale. Use an LF checkout;
CRLF shell inputs are refused rather than rewritten.

Defaults are four compile jobs, at most four test jobs, a 4096 MiB memory
planning budget, and a 40 GiB free-space floor. `MAKEFLAGS`, `TESTSUITEFLAGS`,
`NINJAJOBS` and Python's PGO test process count are explicit. Ninja includes the
book's NINJAJOBS hook. The memory budget is a capacity check, **not a hard memory
limit**; set the disposable builder's memory ceiling separately and measure
peak use. Package recipes are trusted root code; chroot is not a security
boundary. No old `buildvm/prepare-host.sh` or `chain*.sh` wrapper is called.

## Source trust and immutable inputs

Provide all 94 selected archives/patches and the completed export from
[sources/source_lock.py](../sources/source_lock.py). Native13 requires the
exact reviewed source-name set, a complete verification report, per-source
verified evidence or an exact approved provenance exception, and reviewed advisory dispositions. The source verifier
performs the cryptographic checks. The separately reviewed `--lock-sha256`
then pins that exact export; a SHA256 observed after a download is not source
authentication. Missing downloads or incomplete authentication refuse before
preparation. This builder never downloads sources or repairs pins.

Trust classes distinguish publisher OpenPGP, HTTPS-published strong checksums,
and distributor OpenPGP Manifests. The distributor path additionally requires
the approved Gentoo signing root, signed snapshot, exact package Manifest,
source size/SHA512 and the retained linkage. A bare `verified` flag is not a
replacement for that structure or the independently reviewed lock digest.
Make additionally uses a separately verified Gentoo Lzip reference and exact
uncompressed tar equality to the selected gzip archive. Eight unsigned LFS
patches and three Tcl/SQLite/manual inputs have narrowly enumerated provenance
exceptions, not publisher authentication. Their policy digests, source tuples,
retained evidence and required application/test/confinement gates are checked.

The current source export is **build-only**: Expat's residual CPU denial of
service CVE-2025-66382 remains release gate H55. The exact named deferral is
preserved in the build identity and core receipt. Unreviewed advisories and
arbitrary deferrals refuse. Python advisories 088/089 additionally require
the two exact reviewed repo backports and their review digest in the lock.

The source tree, selected book, generated overrides, helpers, native profile,
source lock, all archives, host tools and resource/test policy form one immutable
`root/tup-build/BUILD-INPUTS.json`. Its exact bytes cross into chroot. Full
cached/staged source checks and input recomputation run before and after every
stage, including resume validation. Existing markers alone never authorize
reuse. Changes require a fresh workspace or a separately reviewed restoration
of both target state and evidence.

## Run

After source authentication and disposable-host preparation, use the same
arguments for each action. Replace the digest only after reviewing the export:

```bash
args=(
  --profile lfs-13.1-systemd
  --workspace /srv/tup-build/run-001
  --source /srv/dawnr/tup
  --source-cache /srv/tup-sources
  --source-lock /srv/tup-inputs/sources.lock.json
  --lock-sha256 VERIFIED_LOCK_DIGEST
  --build-user lfs --jobs 4 --memory-mib 4096 --free-gib 40 --through ch08
)
python3 /srv/dawnr/tup/native/build.py preflight "${args[@]}"
python3 /srv/dawnr/tup/native/build.py prepare "${args[@]}"
python3 /srv/dawnr/tup/native/build.py build "${args[@]}"
python3 /srv/dawnr/tup/native/build.py validate "${args[@]}"
```

`--book` may relocate the selected profile's exact extracted book; it does not
approve an arbitrary release. `--through ch06` stops before chroot and emits no
full-core completion export. `prepare` stages inputs and creates target layout.
`build` executes ch05, ch06, ownership, ch07-inner, then ch08 sequentially.
`validate` requires every selected stage to be complete and runs only driver
validation, never a missing package command. Validation still uses a private
mount/PID namespace for the chroot view and can write the validation export.

Chapter 7 ownership/mount/chroot pages are delegated to the checked host runner.
Native13 executes inner pages 5-15, including temporary tool cleanup; manual
exit, host unmount and optional backup examples are omitted. Namespace teardown
releases mounts. Historical12.4 retains its original inner pages 5-12 policy.
No backup operation is claimed by either profile.

## Evidence and recovery

`workspace/state` retains preparation identity, stage intents/results and logs.
A completion record is committed only after successful execution, flushed log
and complete postconditions. The driver keeps per-page transactions in
`root/sources/log`. Required native13 suites additionally preserve original
result files and a checked file manifest under `log/native-suites`; removal,
addition or alteration refuses subsequent validation. Optional suite skips are
explicit receipts, never passes.

Required coverage includes compiler/math suites, Tcl/Expect, both coreutils
privilege phases, final Python, tar, kbd and embedded bzip2 comparisons. Python
backport regressions also run with temporary Python; kbd compiles the 18 affected
keymaps without opening a console. SQLite's shipped shell selftest and bounded
SQL regressions are labeled local coverage: its selected autoconf archive does
not ship the full upstream testfixture suite. Per-test upstream skips remain skips.

A fresh full-core validation exports `state/CORE-COMPLETION.json`, schema
`tup-native-core-completion-v1`, with input identity, completed stage receipts
and logs, canonical driver identities, required-suite evidence and validation
time. This is a **core-only** receipt. It does not attest all installed files or
claim boot, remote access or release eligibility. Boot packaging must require a
successful current `validate` invocation and separately inventory the exported
root, including ownership, modes, links and extended attributes.
The receipt preserves source assurance counts, source release eligibility and
open release gates; core `release_eligible` remains false.

Failed/interrupted preparation or execution, retained writer locks, damaged
receipts, changed inputs and filesystem errors refuse reuse. There is no force
or automatic target deletion. Preserve the failure evidence and investigate;
do not remove locks while a builder may still be running. The first real LFS
build, mount/recovery behavior, peak-resource measurements and all boot/install
and remote-access gates still need runtime evidence.

## Checks

```bash
python3 -m unittest discover -s tup/tests -p 'test_native*.py' -v
bash -n tup/native/run-stage.sh
bash -n tup/native/profiles/lfs-13.1-systemd/required-suite.sh
```

These fixtures use synthetic results and harmless command stubs. They do not
build a package or mount a filesystem. See [VALIDATION.md](VALIDATION.md) for
observed results and limitations. Host/chroot policy follows the official
[13.1 host requirements](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter02/hostreqs.html),
[build environment](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter04/settingenvironment.html),
[kernel filesystems](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/kernfs.html)
and [chroot](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/chroot.html).
