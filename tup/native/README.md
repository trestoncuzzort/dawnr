# Native LFS core builder

This path builds the existing x86_64 LFS recipes into an explicit directory on a
disposable Linux host. It does not create a VM, partition a disk, install a
bootloader or require QEMU. The first implementation stops at chapter 8. That
output is an LFS core, not a bootable native TUP release. Chapters 9 onward need
the native networking, EFI, initramfs, installer and enrollment work tracked in
`../HEADLESS-GOAL.md`.

The old `buildvm/prepare-host.sh` and `chain*.sh` are outside this entrypoint's
dependency graph. No VM device name or physical install target is accepted.
The generated book pages remain unchanged. The native shadow override locks
root instead of assigning the historical shared password.

## Host and resources

Use a dedicated Linux x86_64 builder with ext4 storage, root for orchestration,
and an existing unprivileged `lfs` account for chapters 5 and 6. Host package
installation and account creation are separate bootstrap operations. Python
3.10 or newer runs on the host; the early chroot uses Bash and coreutils only.
The input-aware driver and its entire `buildlib/` directory must be integrated.
The driver requires Bash 4.4 or later and GNU coreutils 8.24 or later for checked
durability operations, beyond the historical book's minimum host versions.
Use a Linux checkout with LF shell files; CRLF scripts are refused, not silently
rewritten. Source, cache and workspace directories must be disjoint.

The preflight checks compiler/tool identities, LFS host requirements, ext4,
mount namespaces, a C++ compile/link, and available CPU/RAM/disk. Default
parallelism is four jobs with a 4096 MiB memory planning budget and a 40 GiB
free-space floor. `MAKEFLAGS` and `TESTSUITEFLAGS` enforce the job count. The
memory number is a capacity check, **not a cgroup hard limit**: set the disposable
builder's RAM ceiling separately and measure actual peak use before accepting
H01. The recipes are trusted root code inside a chroot; chroot is not a security
boundary. Run this in disposable build infrastructure.

## Authenticated source inputs

Supply the complete local source cache and a source lock with a separately
authenticated expected SHA256. The builder never derives trust from a digest
of newly downloaded content and does not fetch missing archives. A provenance
description is an audit reference, not cryptographic proof by itself. Whoever
provisions `--lock-sha256` must verify the publisher's signatures/checksums or
reviewed pinned-source process before supplying that digest.

The lock schema is:

```json
{
  "schema": "tup-source-lock-v1",
  "architecture": "x86_64",
  "book_source_sha256": "<SHA256 of raw book-x86_64/BOOK-SOURCE bytes>",
  "provenance": "<reference to authenticated publisher or reviewed pin evidence>",
  "sources": [
    {"name": "<archive or patch basename>", "url": "https://<publisher>/<file>",
     "sha256": "<independently authenticated SHA256>"}
  ]
}
```

Every book archive named in chapters 5–8 must appear. Include all patches and
other transitive package inputs too; a book's MD5 list alone is insufficient for
this contract. Missing, changed, duplicate and unsafe source records refuse
before preparation. This repository does not yet include an authenticated
native source lock, so no complete native build is claimed.

## Run

Create an empty dedicated workspace under a traversable parent, for example
`/srv/tup-build/run-001`, and keep the source/cache elsewhere. Invoke the same
arguments for each action (replace the placeholder digest only after checking
the lock's provenance):

```bash
python3 tup/native/build.py preflight \
  --workspace /srv/tup-build/run-001 --source-cache /srv/tup-sources \
  --source-lock /srv/tup-inputs/sources.lock.json --lock-sha256 VERIFIED_LOCK_DIGEST
# Repeat with action prepare, then build. --through ch06 stops before chroot.
```

`prepare` copies verified sources and all build inputs into `workspace/root`.
`build` runs ch05, ch06, ownership transfer, ch07-inner, then ch08 synchronously.
Later stages cannot start after a nonzero result. Chroot mounts exist in a
private mount/PID namespace that ends with the stage; there are no asynchronous
marker-polling chains. The selected tests remain `glibc gcc binutils`; other
suite skips stay in the driver's receipts and are not passes.

`--book` selects the location of the extracted x86_64 book. This initial unit
accepts only the historical LFS 12.4 metadata and exact chapter 7 order. Other
books, including 13.1, refuse until their changed packages/crossing are adapted
and tested. This does not approve the retired SysV release for production;
review the maintained book/init policy before the production build. The source
lock binds the selected book's exact identity.

Chapter 7 pages 2–4 are implemented by the ownership/environment/namespace
crossing. Pages 5–12 are the explicit inner sequence. Page 13 combines optional
space cleanup with exiting chroot, host unmounts and a backup; it is deliberately
omitted here instead of executing host-side commands inside the target. The
cross toolchain/docs can therefore remain until a separately receipted final
cleanup is implemented. No completed full chapter-7 cleanup/backup is claimed.

The source tree, full book/overrides/helpers, native scripts/profile, lock,
archives, host toolchain identities and resource/test policy form one immutable
`BUILD-INPUTS.json`. The same bytes are passed as `TUP_BUILD_INPUTS` outside and
inside chroot. Before **every stage and resume**, the caller recomputes current
input identities and validates both cached and staged archive hashes. The Bash
driver may treat that JSON as opaque because this caller checks its contents.
Completed stages require the same inputs, intact logs, and the driver's
`TUP_VALIDATE_ONLY=1` ledger check before they are skipped.

## Evidence and recovery

`workspace/state` holds preparation identity, stage intent/result JSON and
unmodified logs. A completion record is atomically renamed only after the
child succeeded and its log was flushed. Persisting that record is itself a
required operation. `root/sources/log` retains the per-page driver receipts.
The exact ordered source pins are exported as
`root/sources/SHA256-MANIFEST-NATIVE.txt`; altered manifests and any extra staged
source file/directory refuse before a stage starts.
No completion message means native boot/install readiness.

An interrupted preparation, uncertain/failed stage, retained writer lock,
changed input, altered log or corrupted driver ledger refuses reuse. Inspect
and retain that evidence, then start in a new empty workspace. There is no
`--force` option or automatic deletion of the old target root. Do not remove a
writer lock while its build may still be running. Filesystem crashes or changes
to the built tree still require final inventory/boot validation; stage receipts
are not an image-integrity proof.

## Validation

Prediction before running the fixture suite: all source-tamper, stale-input,
failed-child, ledger-validation and receipt-write failures return failure; none
authorizes a completed stage. Successful byte-exact fixture inputs are accepted.
These fixtures never run an LFS page, mount a filesystem or access a device.

```bash
python3 -m unittest discover -s tup/tests -p 'test_native_build.py' -v
bash -n tup/native/run-stage.sh
bash -n tup/native/profiles/x86_64/overrides/x86_64/ch08/shadow.sh
```

Still required: Linux host preflight, mount-namespace failure/recovery tests,
an actual clean chapters 5–8 build, Linux resume/driver integration tests,
resource measurements and all later native installation gates. Windows fixture
success cannot substitute for any of those results.

The host/environment/chroot sequence follows LFS 12.4:
[host requirements](https://www.linuxfromscratch.org/lfs/view/12.4/chapter02/hostreqs.html),
[build environment](https://www.linuxfromscratch.org/lfs/view/12.4/chapter04/settingenvironment.html),
[kernel filesystems](https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/kernfs.html),
and [chroot](https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/chroot.html).
