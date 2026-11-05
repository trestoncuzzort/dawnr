# Disposable image installation with systemd-repart

`image.py` is a small plan/apply adapter around the installed **systemd-repart
255**, with GPT/ESP/ext4 declared through its supported `.conf` interface. It
accepts only an explicitly precreated, all-zero **regular-file image**. It has no
physical disk, USB, mount, loop attachment, NVRAM, download or service operation.
The first real run populated a 200 MiB image and inspected both filesystems
offline. This is an installer foundation, not a bootable TUP installation.

The existing `tup/boot/inputs.py` inventory binds contents, numeric ownership,
modes, timestamps, xattrs, hardlinks and symlinks. Repart supplies partitioning,
filesystem creation and payload copying. TUP-specific code binds the reviewed
plan to its source and exact target, excludes unsafe paths, requires explicit
confirmation and retains failed-attempt evidence. It does not implement a
partition engine, filesystem copier or ACL parser.

## Measured path

Run in the disposable Linux x86_64 builder as root. The qualification creates
only fresh files beneath the requested directory; an existing directory refuses.
Use the existing authenticated host packages: systemd 255, util-linux, e2fsprogs,
dosfstools, mtools, coreutils, acl and libcap. No packages are installed by these
scripts. A version/hash observation does not authenticate a downloaded tool.

```sh
python3 tup/install/qualify.py --workdir "$TUP_FRESH_INSTALL_FIXTURE"
TUP_INSTALL_TEST_ROOT="$TUP_DISPOSABLE_TEST_PARENT" \
  python3 -m unittest discover -s tup/tests -p 'test_install*.py' -v
```

`qualify.py` writes its prediction before executing. It creates a 64 MiB FAT ESP
and 128 MiB ext4 partition in a 200 MiB image. The ESP contains deliberately
nonbootable fixture bytes at `EFI/BOOT/BOOTX64.EFI`. After planning, it compares
the entire image SHA256 with the original. After explicit apply, it uses sfdisk
to inspect GPT, dd to extract the checked partition extents, blkid to identify
the filesystems, debugfs for ext4 metadata, and mtype for the EFI file bytes.
It checks mode 4750, UID 12345/GID 23456, fixed mtime, shared hardlink inode,
relative symlink, user xattr, named-user POSIX ACL and file capability. These are
synthetic fixture IDs, not a deployment identity.

The measured report is [qualification/systemd-repart-255.json](qualification/systemd-repart-255.json).
Full images, plans, inventories and command logs remain private because real
plans contain local paths and exact target identities. `QUALIFICATION.json`
records only the stated fixture properties. No VM boot, kernel enforcement of
those capabilities, whole-TUP tree comparison or physical install is implied.

## Plan and apply contract

Supply a source directory containing exactly `root/` and `esp/`. The caller
provides the separately reviewed SHA256 of
`canonical(tup.boot.inputs.inventory(source))`; this is an integrity identity,
not source authentication. All input/output paths must be disjoint and contain
no symlink components. The ESP rejects unsupported types and case collisions
that FAT might silently omit or collapse. Source inventories reject special
files and nested filesystems; mountinfo also checks same-filesystem bind mounts.

Create the empty image deliberately before planning. This adapter never creates
or resizes it. The accepted range is 200 MiB through 64 GiB in whole MiB; default
ESP/root sizes are 64/128 MiB. Larger fixture sizes are explicit flags, not a
physical layout recommendation.

```sh
python3 tup/install/image.py plan \
  --target "$TUP_EMPTY_REGULAR_IMAGE" --source "$TUP_FIXTURE_SOURCE" \
  --source-sha256 "$TUP_REVIEWED_SOURCE_INVENTORY_SHA256" \
  --state "$TUP_FRESH_INSTALL_STATE" --esp-mib 64 --root-mib 128

# Review PLAN.json, the exact image identity and both partitions first.
python3 tup/install/image.py apply \
  --state "$TUP_FRESH_INSTALL_STATE" --plan-sha256 "$TUP_REVIEWED_PLAN_SHA256" \
  --confirm "APPLY-IMAGE $TUP_REVIEWED_PLAN_SHA256"
```

Planning records inode/device/size/timestamps/full-file SHA256, source inventory,
tool/config/adapter identities, per-plan UUID seed and repart's partition plan.
It invokes an explicitly named regular-file descriptor with `--offline=yes`,
`--empty=require`, `--dry-run=yes`, `--split=no` and fixed definitions. It never
uses repart's implicit current-root target, `--image=`, `--size=`, `--empty=create`
or ambient partition definitions. Temporary filesystem images remain under the
fresh state directory. No preparation-host machine ID supplies the UUID seed.

Apply rechecks the exact plan digest, confirmation, target, source, definitions,
code and host tools. An inode change refuses even if every image byte matches.
Hardlinked targets, attached loop images and mounted paths refuse. A sidecar
lock serializes this adapter; repart owns its own target lock. The inherited
open descriptor pins the target inode passed to the actual tool. Use quiescent,
trusted build infrastructure: this is not a sandbox against another privileged
process changing/restoring input files or replacing tools between observations.
Host runtime libraries remain part of the separate environment review.

Before writing, apply durably records `APPLYING.json`. It compares repart's
reported operation and the actual sfdisk GPT table with the reviewed layout,
flushes the image, rechecks inputs, and atomically publishes `RECEIPT.json`.
The receipt always says `populated-unqualified`, `release_eligible: false`,
`root_contents_attested: false`, `boot_tested: false` and
`physical_install_tested: false`. Successful repart exit plus GPT inspection
does not prove every copied file; the real fixture adds the specific offline
metadata checks above.

An interruption, failed command, full ledger or uncertain receipt persistence
cannot produce a successful return. `FAILED.txt`, logs and the attempt marker
remain. A completion persistence failure withdraws the receipt to
`RECEIPT.uncertain.json`. There is **no automatic resume or overwrite**: preserve
the failed image/state, diagnose, and use a fresh image and reviewed plan. An
orphaned sidecar lock also refuses; retain it while investigating. The tests
inject partial writes and persistence failure; actual power-loss recovery on
disposable block devices is still pending.

## H17/H18 findings and remaining gates

The first real probe disproved the prediction that `--dry-run=yes
--empty=create` was read-only: repart created and populated the image. Upstream
255 and 261 intentionally force dry-run off for `--empty=create`. Also,
`--size=` may grow an image before planning, and `--split=yes` writes partition
files independently of dry-run. The corrected real plan used a precreated file,
`--empty=require` and `--split=no`; its whole-image hash stayed unchanged. These
observed behaviors are regression checks in `test_install_image.py`.

A later metadata check initially compared raw ACL xattr representations and
failed. Debugfs emits zero in unused owner/group/mask/other ID fields, while the
kernel emits UINT32_MAX. The corrected check asks the existing kernel ACL
implementation to validate and canonicalize the extracted ACL on another
disposable regular file, then compares all canonical ACL bytes. Named user IDs
and permissions must still match. The failed run remains evidence.

Before this can install TUP, the completed source-built systemd 261 must actually
contain `systemd-repart` with libfdisk support, plus working target mkfs/mtools
helpers. Repeat this real qualification using those target tools before changing
the current version gate; the Ubuntu 255 result proves only the host path. Then
bind an authenticated TUP export to fresh native validation and boot/remote layer
receipts, carry all source release gates including H55, verify the complete
deployed root, build the installed-root initramfs/EFI configuration, and boot
with reordered SATA/NVMe device models. Root discovery must use persistent
partition/filesystem identities, never `/dev/sda` assumptions.

Physical selection still needs stable serial/WWN identity, running-root/source
media/USB exclusion, a reviewed disk plan, interruption/recovery tests on
disposable devices, boot/remote proofs, and the owner's final exact-target
confirmation. The backup statement does not select a disk. This adapter refuses
physical devices regardless of its image confirmation token; that token cannot
authorize a physical erase. No USB or disk write command is supplied here.

Primary references inspected before implementation: [systemd 255 CLI](https://raw.githubusercontent.com/systemd/systemd/v255/man/systemd-repart.xml),
[systemd 261 CLI implementation](https://raw.githubusercontent.com/systemd/systemd/v261/src/repart/repart.c),
[repart.d copying and layout contract](https://raw.githubusercontent.com/systemd/systemd/v261/man/repart.d.xml),
[systemd build dependency](https://raw.githubusercontent.com/systemd/systemd/v261/meson.build),
[LFS 13.1 EFI GRUB installation](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/grub.html),
[BLFS rescue boot device](https://www.linuxfromscratch.org/blfs/view/stable-systemd/postlfs/bootdisk.html),
[ext4 ACL representation](https://raw.githubusercontent.com/torvalds/linux/v6.18/fs/ext4/acl.c), and
[e2fsprogs metadata population](https://raw.githubusercontent.com/tytso/e2fsprogs/v1.47.0/misc/create_inode.c).
