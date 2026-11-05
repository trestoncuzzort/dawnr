# Target layers on an exported core

`build.py` adds the packages and configuration that turn a validated LFS core
into a bootable, remotely administrable TUP root. It never modifies the core
workspace: the core is revalidated, copied with `rsync` into a new workspace,
and every layer page runs through the unchanged [`driver.sh`](../driver.sh)
inside that copy. No owner is enrolled and no service is started.

This directory was first exercised only by fixtures. Read the status documents
for what has actually run; a zero exit here is not a boot or login result.

## Chapters

A chapter is a directory with an `ORDER` file and page scripts, exactly as in
the core build. Chapters run in this fixed order in one ledger:

| Chapter | Directory | Adds |
| --- | --- | --- |
| `remote` | [`../remote/pages`](../remote/pages) | libmnl, libnftnl, nftables, OpenSSH (installed without host keys), sudo (installed with no rule) |
| `boot` | [`../boot/pages`](../boot/pages) | device-mapper part of LVM2, Linux 6.18.60 with modules, selected firmware, dosfstools 4.2 (`mkfs.fat`, `fsck.fat`, for the disk installer) |
| `system` | `../system/pages` | identity, wired networking, units and the unenrolled access policy, the disk installer (`tup-install`) |

Only a run of all three chapters that also passes the packager's offline-root
and kernel checks writes `BOOT-LAYER.json` (schema `tup.boot-layer.v1`), the
receipt [`boot/assemble.py`](../boot/assemble.py) requires. A partial run is
receipted as `partial-chapters` and cannot be packaged.

libaio is not built. This LVM2 release states in its `configure.ac` that the
device-mapper part builds without it (`make device-mapper`,
`make install_device-mapper`), and no LVM tool or service is installed.

## Page contract

Every page starts with `#!/bin/bash`. A page that builds a package names its
archive on line 2 as `# TUP_TARBALL=<file>`; the driver extracts it into
`/sources` and runs the page inside the extracted tree. Other pages run in
`/sources`. The next line is `source /tup-layer/common.sh`, which enables
`set -euo pipefail` and refuses to run outside the runner.

Inside the chroot a page is root with a cleared environment, no standard
input, a private network namespace containing only loopback, a minimal tmpfs
`/dev`, read-only `/sys`, and tmpfs `/run` and `/tmp`. `TUP_JOBS` is 1 to 4.
The repository's `boot`, `hardware`, `install`, `remote` and `system` directories
are readable at `/tup-layer/tup/` (without their evidence, runtime-test and
pages subdirectories; `HELPERS` in `build.py` names them). `system/pages/04-installer.sh`
installs from `install` and `boot` there. systemd is installed but not running, so pages may only use
offline operations such as `systemctl enable`.

## Running

Run as root in the disposable Linux builder, inside whatever resource limits
the operator applies to the calling unit. The workspace must not exist and its
parent must be a private root-owned directory.

```sh
python3 tup/target/build.py --workspace "$TUP_LAYER_WORKSPACE" \
  --core-validator "$TUP_CORE_VALIDATOR" --cache "$TUP_LAYER_SOURCE_CACHE" \
  --gpg /usr/bin/gpg --jobs 4
```

`--core-validator` is the same `tup.boot-core-validator.v1` file the packager
uses. The cache must hold every archive named by the selected pages plus the
signed Gentoo snapshot used by the distributor-authenticated records (the
Gentoo snapshot also authenticates dosfstools). The `boot` chapter needs
`dosfstools-4.2.tar.gz` (320917 bytes, SHA256
`64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527`) and its
detached `dosfstools-4.2.tar.gz.sig` there. Each
archive is authenticated again on every run: the five remote archives through
[`remote/verify_layer_sources.py`](../remote/verify_layer_sources.py), LVM2,
linux-firmware and dosfstools through their retained records and
[`sources/source_lock.py`](../sources/source_lock.py), and the kernel archive
against its entry in the core source lock. An earlier receipt is never reused.

## Evidence

The workspace keeps, outside the exported root: the core completion receipt
and its validation log, `SOURCE-VERIFICATION.json`, the export log, full
`before.json`/`after.json` inventories with `changes.json`, the staged
execution inputs and their manifest `BUILD-INPUTS.json`, the layer ledger with
every page log under `sources-and-ledger/log`, `target-build.log`, and
`TARGET-LAYERS.json`. Extra files that pages retain in the ledger directory
(upstream test logs, the firewall probe result, the hashes of the OpenSSH
programs taken before its test suite ran) are hashed into that receipt.

A failed run leaves its workspace for diagnosis. There is no resume: the
driver refuses a failed or changed page, and a new run needs a new workspace.

## Boundaries

- The chroot and namespaces separate a build from the builder's devices and
  network; they are not a sandbox against hostile sources. Inputs are
  authenticated before use for that reason.
- Package suites that need a booted target (the LVM2 device suite, the full
  nftables kernel suite) are not run here and are recorded as not run.
- LVM2, linux-firmware and dosfstools have source authentication but no separate
  advisory review yet; the receipt says so.
- `04-installer.sh` and `04-dosfstools.sh` have run only in a host rehearsal and
  against fakes. Nothing shows yet that the installer works on a real disk.
- The kernel is configured from the reviewed fragments by the target toolchain
  and rechecked by both configuration checkers. The retained Kconfig
  qualification used the builder's compiler and is not assumed to be equal.

## Checks

```sh
python3 -m unittest discover -s tup/tests -p 'test_target*.py' -v
bash -n tup/target/run.sh tup/target/common.sh
```

Sources: the [LFS 13.1 kernel page](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/kernel.html),
BLFS 13.1 [LVM2](https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/lvm2.html),
[firmware](https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/firmware.html) and
[OpenSSH](https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/openssh.html) pages,
[unshare(1)](https://man7.org/linux/man-pages/man1/unshare.1.html) and
[rsync(1)](https://download.samba.org/pub/rsync/rsync.1).
