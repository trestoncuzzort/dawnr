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

# Whole-disk installer: `disk.py`

`disk.py` installs the running live system onto one whole internal disk, from
the live system itself, as root. It is not interactive, uses no network and
writes no firmware variable. `image.py` above is unchanged and still refuses
every physical device; `disk.py` is the separate real-device path the hurdle
register (H10, H11, H17, H18) asked for.

**State on 2026-11-05: written and tested against recorded fakes and against
real `sfdisk`, `mkfs.ext4`, `mkfs.fat`, `blkid`, `cpio`, `grub-script-check` and
`grub-mkstandalone` on regular files. It has never touched a block device,
never run inside the live image and never booted an installed disk.** Section
"Not yet shown" lists what only a VM and then the desktop can show.

The image ships it (`system/pages/04-installer.sh`): the script and the two boot
modules it imports are under `/usr/lib/tup-installer/tup/{install,boot}/`, and
`/usr/sbin/tup-install` runs it with `python3 -I -B` and that explicit path.
`tup/system/README.md` has the owner's short version, "Installing to a disk".

```sh
tup-install plan  --target /dev/nvme0n1 --source /run/rootfsbase --output /root/plan.json \
    [--esp-mib 512] [--enroll-input DIR] [--state DIR] [--allow-existing]
tup-install apply --plan /root/plan.json --confirm TOKEN --state /root/install-state-1
```

`plan` prints a summary that ends with `Confirmation token: SERIAL-XXXXXXXX`.
`--allow-existing` lets a plan replace a disk that holds data. **No option lets
it replace a disk that looks like Windows** (next section).

## What `plan` does and records

`plan` runs only commands whose exact shapes `read_only_command()` lists
(`lsblk --json --bytes -o ...`, `sfdisk --dump|--json`, `wipefs --no-act
--json`, `blkid -p -o export`, and version probes). A wrapper raises before
executing anything else, and the tests drive `plan` through a fake host in which
every write-capable tool would be recorded: none ever is. The tests judge that
with their own literal list of read-only shapes, not with `read_only_command()`,
so a mistake in the production predicate cannot hide a write from them. The one
other look at the disk is `Host.read_block()`: the first and last 1 MiB, opened
`O_RDONLY` and read with `pread`, never through a tool that could write.

It stores in `PLAN.json`: the whole-disk identity (kernel name, vendor, model,
serial, WWN, size in bytes, logical and physical sector size, transport,
removable, hotplug, read-only, partition-table type and every partition with its
filesystem facts), the `sfdisk --dump` text, every `wipefs` and `blkid` signature
of the disk and of each partition on it, the offset of the first non-zero byte and
the SHA256 of the first and of the last MiB, and a digest of all of that; the disks
in use by this system; the source's mount, inventory digest, entry and byte counts;
the kernel release and image digest; the microcode decision; the enrollment
input's file digests and what `enroll.py` accepted from it (account, scope, clock,
key fingerprints); every identifier of the new disk (disk GUID, both partition
GUIDs, the FAT volume ID, the ext4 UUID); the exact `sfdisk` script, `fstab` and
`grub.cfg`; and the path, SHA256 and reported version of every tool. The plan's
digest covers all of it.

## What it refuses

Each case is a unit test with zero write commands recorded.

- **A disk that looks like Windows, always.** `plan` refuses, with or without
  `--allow-existing`, any disk on which `wipefs`, `blkid`, `lsblk` or the partition
  table shows an `ntfs`, `BitLocker`, `ReFS` or `exfat` signature (libblkid 2.42.4's
  own names for them; an LDM signature too), or a partition of type
  *Microsoft basic data* `EBD0A0A2-B9E5-4433-87C0-68B6B72699C7`, *Microsoft
  reserved* `E3C9E316-0B5C-4DB8-817D-F92DF00215AE`, *Windows recovery environment*
  `DE94BBA4-06D1-4D40-A16A-BFD50179D6AC`, and also *Microsoft LDM metadata*
  `5808C8AA-7E8F-42E0-85D2-E1E90434CFB3`, *Microsoft LDM data*
  `AF9B60A0-1431-4F62-BC68-3311714A69AD` and *Microsoft Storage Spaces*
  `E75CAF8F-F680-4CEE-AFA3-B001E56EFC2D` (the last three are in the same table and
  are what the LDM and Storage Spaces formats use), or an MBR partition of type
  `07` (HPFS/NTFS/exFAT), `27` (hidden NTFS WinRE) or `42` (SFS, the Windows dynamic
  disk). The identifiers are copied from util-linux 2.42.4,
  [`include/pt-gpt-partnames.h`](https://github.com/util-linux/util-linux/blob/v2.42.4/include/pt-gpt-partnames.h)
  and [`include/pt-mbr-partnames.h`](https://github.com/util-linux/util-linux/blob/v2.42.4/include/pt-mbr-partnames.h),
  the tables `fdisk` and `sfdisk` print; the signature names are the `.name` of
  `libblkid/src/superblocks/{ntfs,bitlocker,refs,exfat}.c`. The message says that
  this installer never erases a disk that looks like Windows and that such a disk
  must be cleared by the owner by other means first. `apply` repeats the refusal
  from its own fresh read. There is no `--allow-windows` or similar: the only way
  past this refusal is not to point the installer at that disk. (The test that
  proves it passes `--allow-windows` and expects an argument error.) Windows that
  only a *partition* node reveals (the table and `lsblk` say Linux, `0FC63DAF`, and
  `wipefs` or `blkid` on `/dev/NAMEpN` reports BitLocker, ntfs, ReFS or exFAT) is
  refused the same way, in `plan` and again in `apply`; the probes cover every node,
  and a test that probes only the whole disk fails.
- **A protective MBR with no readable GPT, always, with no flag.** When both GPT
  headers are bad, or both entry arrays fail their CRC, the kernel shows no
  partitions and nothing in the disk can be probed; the protective MBR (partition
  type `ee`) is all that is left of what may be a Windows disk. `plan` and `apply`
  refuse a disk when `sfdisk --dump` prints `label: dos` with a type `ee` partition,
  when `blkid` or `lsblk` reports `PTTYPE` `PMBR`, or when `wipefs` reports a `PMBR`
  signature on a node without a `gpt` signature on that node. The message says that
  this installer never erases such a disk, that it may hide Windows partitions, and
  that the owner must clear it by other means first. A healthy GPT disk is not
  affected (`wipefs` lists `gpt` twice and `PMBR` on every one) and goes through the
  rules above and below. The fixtures are the real output of util-linux 2.39.3 on 128 MiB
  regular files, kept verbatim in the tests: one with LBA 1 and the last LBA zeroed,
  one with both entry arrays inverted (the two print the same), and the healthy
  tables; the protective MBR is
  [UEFI 2.10 section 5.2.3](https://uefi.org/specs/UEFI/2.10/05_GUID_Partition_Table_Format.html).
- **A `--state` directory or `plan --output` file in the wrong place**, in `plan` and
  again in `apply`: on the target disk, on a disk that looks like Windows (or has a
  protective MBR without a GPT) by the same evidence as above, or on a filesystem of
  type `ntfs`, `ntfs3`, `fuseblk`, `fuse.ntfs-3g`, `exfat`, `vfat` or `msdos`. A volatile
  filesystem (`tmpfs`, `ramfs`, or the live overlay whose upper layer is one) stays
  allowed with the VOLATILE notice, and so does an ordinary Linux filesystem on another
  disk that does not look like Windows. A mounted filesystem of the target is
  refused earlier still, as "in use by this system".
- A target that is not a kernel name below `/dev` (by-id symlinks, relative
  names, anything whose `realpath` differs), not a block device, a partition,
  loop, device-mapper, md, zram, nbd, floppy or optical device (`lsblk` TYPE and
  name and sysfs `loop`/`dm`/`md`/`partition` markers), or read-only (`lsblk` and
  sysfs `ro`).
- A disk with a mounted partition (`lsblk`), a swap area on it, a
  device-mapper or md device holding it or one of its partitions (sysfs
  `holders`), or that is in use by this system in any way: every
  `/proc/self/mountinfo` row, every swap area, the source and the overlay's
  `lowerdir`/`upperdir`/`workdir` are resolved to whole disks through
  `/sys/class/block` and `/sys/dev/block`, through partitions, `slaves` and loop
  `backing_file`, repeatedly. In the Ventoy layout the running root, the
  squashfs loop, the ISO loop and the stick's data partition all end at the stick.
  This fails closed in three places that used to fail open: a loop device whose
  backing file is a block special file (`losetup /dev/loop3 /dev/sdX`) is resolved
  through the node's `st_rdev`, because its `st_dev` is the devtmpfs; a mount row
  with a major-0 device number whose source is a `/dev` path (FUSE `fuseblk`
  NTFS or exFAT, btrfs) is resolved through that source; and a major-0 row whose
  filesystem type is not in a fixed pseudo-filesystem set (`tmpfs`, `proc`,
  `sysfs`, `devtmpfs`, `overlay`, `cgroup2` and the like, `PSEUDO_FILESYSTEMS`) and
  whose source is not a `/dev` path (NFS, 9p, sshfs) is a refusal, not a guess.
  A path whose device number is not in the mount table is a refusal too. A mount
  whose disk cannot be determined (for example a loop backing file that no
  longer resolves) refuses instead of being ignored.
- A source that is not exactly a read-only `squashfs` or `erofs` mount point, which
  also refuses `--source /` (the running overlay carries enrollment state and
  host keys), or that fails `check_offline_root` (machine ID, SSH host keys,
  locked root, `ID=tup`), already holds `etc/tup/owner-enrolled.json`, holds
  anything in `etc/tup/enroll-input`, has an `etc/tup` that is not a real directory
  owned by the installing user and closed to group and other writers (`enroll.py`
  would refuse to enroll below it), has no single `/boot/vmlinuz-RELEASE`, or whose
  kernel fails `check_kernel`.
- **A disk that has data**, unless `--allow-existing` is given; then `PLAN.json`
  and the summary list each item in words under "this will ERASE". Data is a
  partition table (also an unreadable one), a partition, any `wipefs` signature, any
  `blkid` hit, **any non-empty `pttype`, `ptuuid`, `fstype`, `uuid`, `partuuid` or
  `label` that `lsblk` reports** (it reads the udev database, the others read the
  device; a disagreement is not blank), and **unrecognised non-zero data**: a disk
  with no table and no signature counts as blank only if a read-only sample of its
  first 1 MiB and last 1 MiB is all zero bytes. A non-zero byte there is listed as
  "unrecognised non-zero data in the head/tail of the disk ... first non-zero byte at
  offset N". This matters because the install target is reported RAW by Windows,
  which proves nothing: RAW also describes an encrypted or foreign volume. Only
  those two regions are sampled; the bytes between them are not read.
- A disk with neither serial nor WWN (it could not be named in the token), one too
  small for the live root plus 15 % and 512 MiB, `--esp-mib` outside 64-8192, or an
  ESP too small to be FAT32 on the disk's sectors. `mkfs.fat -F 32` makes a volume
  with fewer than 65525 clusters anyway and only warns, so `make_layout` refuses it:
  at 512-byte sectors the floor is 66592 sectors (below the 64 MiB minimum) and at
  4096-byte sectors 65696 sectors, so `--esp-mib 257` or more. Both numbers were
  found by bisection with `mkfs.fat 4.2` on regular files, and a test redoes it.
- An enrollment input that `enroll.py` would refuse at the first boot of the
  installed system: `plan` runs `enroll.py`'s own `plan()` on it (the repository's
  copy, or `/usr/lib/tup/remote/enroll.py` in the image), so an RSA key or a
  `clock` file that does not say `utc` is refused now and not on a headless
  machine. The input holds `authorized_keys` and optionally `owner`, `listen`,
  `peer` and `clock`, the five names `enroll.py` reads. **Any other name is
  refused**, not copied silently; the only names ignored are macOS metadata,
  `.DS_Store` and `._*`, and the plan and the summary list what was ignored.

## The token and `apply`

The token is the disk serial (WWN if there is no serial; characters outside
`A-Za-z0-9._-` become `_`) joined with the first eight hex digits of the plan
digest. It is not stored in `PLAN.json`; `apply` computes it from the identity it
reads again and compares in constant time. A plan for disk A therefore cannot be
confirmed with disk B's token, and an edited plan changes its digest. Virtio disks
need a `serial=` option in QEMU or `apply` has nothing to name; real SATA and NVMe
disks report one.

`apply`, in this order, writing nothing until the intent record exists:

1. Load the plan; refuse if its digest, basis digest or generated texts do not
   match its fields.
2. Refuse if the state directory exists (printing the intent and last journal
   line it holds) or its parent is not an existing real directory.
3. Re-measure the tools, then **all the slow work**: recompute the source inventory,
   kernel and microcode, the enrollment input (with `enroll.py`'s `plan()`) and the
   installer's own digests.
4. **First recheck** (`recheck()`): re-read the identity and the complete state,
   including the sample, and refuse on any difference from the plan (serial, WWN,
   size, sector size, table, any signature, any non-zero byte that moved, mounts,
   holders); refuse if `/dev/NAME` is not the planned device number; repeat the
   Windows and protective-MBR refusals on this fresh read; refuse a `--state` parent on a
   Windows-style filesystem, on the target or on a Windows-looking disk; refuse on a wrong token; refuse if the set of
   disks in use changed or any safety check fails; refuse if the source mount
   changed.
5. `mkdir` the state directory (0700), write and fsync `INTENT.json`.
6. Build the boot files inside the state directory (`grub.cfg` checked with
   `grub-script-check`, `grub-mkstandalone` image, microcode cpio). These run
   minutes after step 4 on a slow machine and write nothing to the target.
7. **Second recheck, then the first write.** Immediately before `sfdisk`, with the
   journal line as the only thing between them, `recheck()` runs again (a review
   showed that a disk swapped while step 6 ran was not noticed). Then `sfdisk --lock
   --wipe always --wipe-partitions always DISK` with the planned script on
   standard input; `udevadm settle`; the new partitions' device nodes are found from
   sysfs (partition number, start and size in 512-byte units must equal the plan,
   and the nodes must exist), never by appending a digit; `sfdisk --json` must show
   exactly the planned GUIDs, types, names, starts and sizes.
8. Before **each** `mkfs`, the node is confirmed again: it is a block device, its
   `st_rdev` equals the `dev` file of that partition in sysfs, `/sys/dev/block/MAJ:MIN`
   reaches the same partition, and its start and size are the planned ones. Then
   `mkfs.fat -F 32 -i VOLUMEID -n TUP-ESP`, `mkfs.ext4 -F -q -U UUID -L TUP-ROOT`,
   `udevadm settle`, and `blkid -p` must report the planned type, UUID and label.
9. Mount the root and the ESP below the state directory (each mount point is
   recorded before `mount` runs); each mount is checked against
   `/proc/self/mountinfo` for the right device number and filesystem.
10. `cp -a --one-file-system SOURCE/. ROOT/`. Then `inventory()` of the copy must equal
    the source inventory except that `lost+found` (made by `mke2fs`) exists.
11. Write `etc/fstab`; create `boot/efi` if missing; refuse if the copy holds a machine ID or SSH
    host keys; if an enrollment input was planned, make `etc/tup` (0755) and
    `etc/tup/enroll-input` (0700) where they are missing, set the latter to 0700 where
    it exists, write its files (including `clock`) 0600, and read owner and mode of
    all of them back (root-owned, those modes, `etc/tup` closed to group and others).
12. Write `EFI/BOOT/BOOTX64.EFI`, the kernel and `amd-ucode.img` on the ESP.
13. Verify the root after the ESP files are written. Each file under `etc/tup/enroll-input`
    is hashed again against the plan and owner and mode are read back a second time.
    `inventory()` of the root is then compared with the inventory of the copy plus the
    planned additions: the paths the installer touches are `etc`, `etc/fstab`, `boot`,
    `boot/efi`, and, with enrollment, `etc/tup`, `etc/tup/enroll-input` and each file
    written (`lost+found` is already in the copy). **They are allowed whether or not they
    existed in the source:** a directory that already exists (the image ships `/etc/tup`
    with `firewall.nft` and an empty `authorized_keys` directory) changes its mtime when
    a file is created in it, and the earlier version refused such a source only after
    `sfdisk` had run. But a planned directory may differ only in its mtime (and takes the
    planned mode), a planned file must be a root-owned regular file of the planned mode
    and digest, and every other entry, so every name below a planned directory, must be
    exactly as copied: a stray file in `etc`, `etc/tup` or `etc/tup/enroll-input`, or
    a changed mode of any of them, is refused. (The earlier version exempted these paths
    from every attribute.) The fstab and every ESP file are read back and compared.
14. `sync`, unmount (ESP then root), `e2fsck -f -n`, `fsck.fat -n`, `blkid -p` and
    `sfdisk --json` once more, `sync`.
15. Only now write `RECEIPT.json` (`tup.install-receipt.v1`): plan digest, target
    identity, every created identifier and device node, source, copy and deployed
    inventory digests, the digest of each boot file and of `grub.cfg`, tools with path,
    digest and version, where the state directory lives, timestamps, and
    `boot_tested: false`, `release_eligible: false`.

`PROGRESS.jsonl` (fsynced before each step) and `COMMANDS.jsonl` (argv, exit status,
bounded output) stay in the state directory. A failure writes `FAILED.json` naming the
step.

**Signals and mounts.** `sfdisk`, `mkfs.fat`, `mkfs.ext4` and `cp` run in their own
session (`start_new_session`), so a Ctrl-C or hangup aimed at the installer does not reach
them mid-write. When the installer itself is signalled meanwhile (`SIGINT`, or `SIGTERM`
and `SIGHUP`, which are converted to an exception) it waits for that child to finish
instead of killing it, and a repeated signal does not abandon the wait: only `SIGKILL` of
the installer does, and the child then finishes on its own. Every mount below the state
directory is then released on every exit path: cleanup reads the mount table and unmounts
each row latest first, whether or not this run recorded it (the point is also recorded
before `mount` runs, as the fallback if the table cannot be read), each attempted even if an
earlier unmount fails, and it retries an unmount that failed earlier in the run.
`SIGINT`, `SIGTERM` and `SIGHUP` are ignored while that cleanup runs. If a mount
cannot be released the run says which, loudly, and leaves it for the operator. `SIGKILL` or
power loss cannot be handled; the mounts then die with the live system.

**Interrupted runs are never resumed.** A second `apply` with the same state directory
refuses and prints the recorded intent. A second `apply` with the same plan and a new
state directory refuses because the disk no longer matches the plan (unless the run was
stopped before `sfdisk` wrote, in which case nothing was written and it may proceed).
Recovery is a new `plan --allow-existing`, which lists what the interrupted attempt left.

**Where the state lives.** The state directory is on the live system's RAM overlay
unless the owner chooses another filesystem; surviving a power cut is not claimed, only
that the disk drifts away from the plan. `plan --state DIR` says in its summary whether
DIR is on volatile storage (`tmpfs`, `ramfs`, or an overlay whose upper layer is one), the
receipt records the same for the `--state` given to `apply`, and without `--state` the
summary says that it does not know. Nothing refuses a volatile state directory; a state
directory on the target, on a Windows-looking disk or on a Windows-style filesystem is
refused (see "What it refuses").

## Why these choices

**`cp -a --one-file-system`.** GNU `-a` is `-dR --preserve=all`: ownership (cp runs as
root), modes, timestamps, symbolic links as links, hardlinks within the copy, and xattrs
and ACLs (`system.posix_acl_*`, `security.capability`). The claim is verified, not
assumed: on the builder (coreutils 9.4) a tree with a setuid file, a file capability, an
ACL entry, user xattrs, a hardlink, a symlink and fixed nanosecond timestamps copied with
exactly this command gives an identical `inventory()`. `apply` repeats that comparison on
the real copy, so a cp that drops one attribute fails the run. The source is the squashfs
lower root, so none of the overlay's upper layer (machine ID, host keys, enrollment
marker) can be copied; the second `--one-file-system` guard stops a stray nested mount.

**GRUB route: `grub-mkstandalone`, not `grub-install`.** The GRUB 2.14 manual documents
`grub-install --efi-directory=DIR --boot-directory=DIR/boot --removable` for removable
installs, and `util/grub-install.c` shows `--removable` forcing `EFI/BOOT/BOOTX64.EFI` and
never calling `efibootmgr` (the `if (!removable && update_nvram)` branches), so it would
also leave firmware variables alone. It still probes the device topology of the ESP with
`grub-probe`, writes a `device.map` and a `/grub` tree, and its image finds its files by
a UUID search it generates. `grub-mkstandalone` (same source tree, same 2.14 build) embeds
one `grub.cfg` and all modules in the image itself, takes no device argument, probes
nothing and is byte-reproducible (two runs on the builder with GRUB 2.14 compared equal;
3.87 MB, PE32+ x86-64 EFI application). The command line lists no `--modules`, so
every module, `smbios` and `serial` included, is in the image; if modules are ever listed
explicitly the list must contain at least `part_gpt fat search linux smbios serial`.
The tradeoff is that changing the menu means rebuilding `BOOTX64.EFI` with the same
command. The target's GRUB is built for `x86_64-efi` only (the audit entry omits the BIOS
and i386-efi builds), which is exactly the platform used.

**`grub.cfg` and the console policy.** It mirrors `boot/assemble.py` `grub_config()`, the
live ISO's menu (README "Boot menu and consoles"). Output goes to the screen and the
serial port (`serial --unit=0 --speed=115200 ...`, `terminal_output console serial`);
input comes from the local console only (`terminal_input console`), because noise on an
absent or unconnected UART could stop the three-second countdown of a headless boot. There
are two entries with the same kernel line, `linux /tup/vmlinuz-RELEASE
root=PARTUUID=<root GUID> rootwait ro systemd.gpt_auto=0`, `initrd /tup/amd-ucode.img`:

| Entry | id | Ends with | Why |
| --- | --- | --- | --- |
| TUP (boot messages on the screen) | `tup` | `console=ttyS0,115200n8 console=tty0` | the default; the last `console=` is `/dev/console`, and the desktop is watched on its screen |
| TUP (diagnostics on the serial port) | `tup-serial` | `console=tty0 console=ttyS0,115200n8 systemd.log_target=console` | a test VM is read through its serial port |

GRUB picks the second by itself when the SMBIOS system manufacturer is `QEMU`
(`insmod smbios`, `smbios --type 1 --get-string 4 --set tup_system_manufacturer`, GRUB
manual "smbios"); if the command fails the screen entry stays the default. (`rd.debug`,
which the live menu adds, is a dracut option and the installed system has no initramfs.)
**There is no `rescue.target` entry.** Root is locked, so `sulogin` would refuse and could
hang a headless machine. **`systemd.gpt_auto=0` is on both lines:** the root and the ESP
have GPT types that `systemd-gpt-auto-generator` recognises, and the ESP is mounted from
`/etc/fstab` at `/boot/efi`; the generator only skips the ESP when `/boot` or `/efi` is in
fstab, so without the option it could mount the ESP a second time at `/efi`
([systemd-gpt-auto-generator(8)](https://www.freedesktop.org/software/systemd/man/latest/systemd-gpt-auto-generator.html):
"it is enabled by default, and a false value may be used to disable it (e.g.
`systemd.gpt_auto=0`)"; listed in
[kernel-command-line(7)](https://www.freedesktop.org/software/systemd/man/latest/kernel-command-line.html)).
The kernel is on the ESP, copied from `/boot`, so GRUB reads only FAT32. The generated file
passes the pinned GRUB 2.14 `grub-script-check` (a test runs it) and builds with the exact
`grub-mkstandalone` argv.

**Does GRUB 2.14 read the ext4 that `mkfs.ext4` makes?** By its source, yes for the
book's feature set: `grub-core/fs/ext2.c` supports the INCOMPAT features filetype,
extents, flex_bg, meta_bg, 64bit and encrypt and ignores recover, mmp, csum_seed and
largedir; `metadata_csum` is RO_COMPAT and does not block reading; the book's e2fsprogs
page (1.47.x) says `metadata_csum_seed` is in the default `ext4` list. That was read, not
run, and it does not matter here: GRUB never opens the root partition. The kernel reads it.

**AMD microcode.** `microcode_cpio()` writes an uncompressed `newc` archive holding
`kernel/x86/microcode/AuthenticAMD.bin` (the container
`usr/lib/firmware/amd-ucode/microcode_amd_fam19h.bin`, checked for the `DMA\0` signature)
after the directories `kernel`, `kernel/x86`, `kernel/x86/microcode`, which the kernel's
early loader reads from the start of the initrd
([docs.kernel.org](https://docs.kernel.org/arch/x86/microcode.html)). The target has no
`cpio`, so the archive is written by about 15 lines of Python; the tests read it back with
a small parser and, where GNU cpio 2.15 exists, with `cpio -it` and `cpio -id`. With no
other initrd the kernel unpacks the archive into rootfs, finds no `/init` and continues to
`root=`. If the container is missing from the source the plan says
"AMD microcode is NOT loaded", `grub.cfg` has no `initrd` and the receipt says so.

**fstab.** `UUID=<root> / ext4 defaults,errors=remount-ro 0 1` and `UUID=<ESP> /boot/efi vfat
umask=0077,rw,relatime,codepage=437,iocharset=iso8859-1,nofail,x-systemd.device-timeout=10s 0 2`.
The options after the book's `codepage`/`iocharset` line are the owner's `umask=0077` and
`nofail` plus a ten second device timeout: a missing ESP must not hold a headless machine in
emergency mode. `/etc/machine-id` stays as the source has it (empty), so the first boot
creates a unique one; no SSH host key is copied (`check_offline_root` and `apply` both
refuse them), so the first boot creates those too.

**Enrollment.** `etc/tup/enroll-input` is the last of `enroll.py`'s `INPUT_DIRECTORIES`: on
the first boot of the installed system `tup-enroll.service` finds `authorized_keys` there
(no stick is needed) and enrolls the owner exactly as it does from a stick. The files the
installer copies are the ones `plan()` of `enroll.py` reads, including `clock`.

## Measured, and not

| Ran | Where | Result |
| --- | --- | --- |
| `tests/test_install_disk.py` | Linux builder (Python 3.12, GRUB 2.14 tools on `PATH`) and Windows (Python 3.13) | 73 tests, none skipped on the builder; on Windows 32 run and 41 skip (apply, the real tools and the signal tests need POSIX). The whole suite on the builder: 561 tests, 1 skipped (the nft check-mode test, which needs an nft binary) |
| `sfdisk` (util-linux 2.39.3) applies the generated script to a regular file; `sfdisk --json` shows the planned GUIDs, offsets and sizes; the last partition ends on a 1 MiB boundary inside the usable range | builder, regular file | pass; the 4096 byte sector layout is computed (4096 only by arithmetic, not by `sfdisk`) |
| `mkfs.fat 4.2 -S 512` and `-S 4096` around the FAT32 floor | builder, regular files | 66591/66592 sectors (512) and 65695/65696 sectors (4096) are the last that warn and the first that do not; `disk.FAT32_FLOOR` |
| `mkfs.ext4 -U -L`, `mkfs.fat -F 32 -i -n` on 64 MiB files; `blkid -p` reports the planned UUID, volume ID and label; `e2fsck -fn`, `fsck.fat -n` accept | builder | pass |
| `grub-script-check` on the generated `grub.cfg`; `grub-mkstandalone` with the exact argv `apply` uses | builder, host-built GRUB 2.14 | pass; 3866624 bytes, `MZ`, reproducible, the same with an empty `PATH` (no external `tar`); `smbios.mod` and `serial.mod` exist for `x86_64-efi` |
| Real `lsblk --json --bytes -o ...` parsed by `read_identity`, real mount table and sysfs resolved by `disks_in_use` | builder (WSL), read-only, earlier run | parsed; resolved `/` to its disk; its overlay `lowerdir` path did not exist in this namespace and so correctly refused |

Not run: any write to a `/dev` node, a loop device, a mount of what the installer made, QEMU,
Ventoy, the installed system booting, `tup-enroll.service` reading the new input directory,
`04-installer.sh` in the layer runner, and the installer inside the TUP image.

Not covered: the disk is re-read just before `sfdisk`, not held open, so a device that is
renamed, swapped or replugged in the moments between that last recheck and `sfdisk` opening
`/dev/NAME` is not caught (holding it open exclusively would make `sfdisk`'s re-read of the
partition table fail).

## Not yet shown (what only a VM and then the desktop can show)

- That `/run/rootfsbase` in the booted live image is a read-only `squashfs` mount point, that
  `disks_in_use` resolves the real Ventoy chain (loop `backing_file` paths as the kernel
  prints them after `switch_root`) and the plan names the stick as in use. With
  `rd.live.ram` the ISO is unmounted and copied to RAM, leaving no mount or loop that points
  back at the stick; the live menu sets `rd.live.ram=0`, and the VM plan checks it.
- That the ISO's squashfs lower root passes `check_offline_root` and `check_kernel` as booted.
- That `sfdisk`, `udevadm settle` and the kernel produce `/dev/vdXN`, `/dev/nvme0n1pN` and
  `/dev/sdXN` in time (thirty one-second polls) and that `wipefs`/`blkid` read-only probes
  and the `O_RDONLY` sample behave on real devices.
- That `mount -t vfat -o umask=0077,codepage=437,iocharset=iso8859-1` and the `fsck.fat -n`
  / `e2fsck -fn` pass on what `mkfs` made, and that the full copy completes in the live
  system's RAM and time limits.
- That firmware starts `EFI/BOOT/BOOTX64.EFI`, the menu appears, GRUB's `linux` loads the
  kernel from FAT, the kernel mounts `root=PARTUUID=` without an initramfs, and the early
  microcode is applied (`dmesg` shows `microcode: ... updated early`).
- That `systemd` runs correctly from the copied root: no live-only units misbehave, an empty
  `/etc/machine-id` is committed on the first boot, `tup-enroll.service` finds
  `etc/tup/enroll-input` and SSH comes up with the USB stick removed; that the ESP is
  mounted exactly once, at `/boot/efi` (`findmnt`), and `/boot` still shows the kernel
  files; and that `smbios` works in the firmware (the QEMU entry is the default under QEMU).
- Windows on the SATA SSD is not touched: only a run of the plan on the real machine, with the
  NVMe selected by its serial, can show the Windows disk is listed as in use or unrelated
  and that nothing on it changes. With the sibling disk targeted by mistake the plan must
  refuse as a Windows disk, flag or no flag.
- That firmware picks `\EFI\BOOT\BOOTX64.EFI` from the NVMe when the Windows boot entry is
  first in NVRAM: no NVRAM entry is written, so the owner uses the firmware boot menu or sets
  the order.

## VM test plan for the integrator

Not run. It uses the real options of `tup/boot/tests-runtime`: `uefi.sh KIND MEDIA SHA256
FRESH_OUTPUT [--memory-mib 512-4096] [--cpus 1-4] [--boot-budget S] [--ssh-port P] [--owner NAME]
[--ssh-wait S] [--poweroff-budget S] [--enroll-keys DIR]` and `remote_check.py
prepare|verify|conclude` (`prepare --output DIR --port P [--owner NAME]`, `verify --output DIR
--port P --owner NAME --wait S`), with the same machine arguments as `uefi.sh`: QEMU 8.2,
`-machine pc-q35-8.2,accel=tcg -cpu max`, `-nodefaults`, OVMF 4M code and a private copy of the
variables, one user-mode network with `restrict=on` and a single loopback forward, `-qmp
unix:DIR/qmp.sock,server=on,wait=off`, `-serial file:`. `uefi.sh` only runs fixed scenarios, so the
install scenarios below launch QEMU with the same arguments. Run as root on the Linux test host,
one QEMU at a time, 2048 MiB.

```sh
export TUP_ISO=...   TUP_ISO_SHA256=...        # the ISO that contains /usr/sbin/tup-install
export W=$TUP_VM_RUNS/install-01  PORT=2224    # W must not exist
mkdir -m700 "$W" && cp /usr/share/OVMF/OVMF_VARS_4M.fd "$W/OVMF_VARS.fd"
OVMF=/usr/share/OVMF/OVMF_CODE_4M.fd
```

**0. Fixtures.** Foreign disks that must never change. The first is a Linux disk (needs
`--allow-existing`), the second looks like Windows (refused with or without it), the third
has no table and no signature but non-zero bytes (needs `--allow-existing`):

```sh
truncate -s 2G "$W/foreign.raw"
sfdisk -q "$W/foreign.raw" <<'EOF'
label: gpt
label-id: 0f0f0f0f-1111-4222-8333-444444444444
start=2048, size=2097152, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=0f0f0f0f-aaaa-4bbb-8ccc-dddddddddddd, name="FOREIGN"
EOF
mke2fs -q -t ext4 -E offset=1048576 -L FOREIGN -U 0f0f0f0f-bbbb-4ccc-8ddd-eeeeeeeeeeee "$W/foreign.raw" 1G
printf 'foreign\n' > "$W/marker.txt"
debugfs -w -R "write $W/marker.txt marker" "$W/foreign.raw?offset=1048576"
truncate -s 2G "$W/windows.raw"
sfdisk -q "$W/windows.raw" <<'EOF'
label: gpt
label-id: 0f0f0f0f-2222-4222-8333-444444444444
start=2048, size=204800, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, name="Microsoft reserved partition"
start=206848, size=2097152, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name="Basic data partition"
EOF
truncate -s 2G "$W/raw.raw"; head -c 4096 /dev/urandom | dd of="$W/raw.raw" bs=4096 conv=notrunc status=none
sha256sum "$W"/foreign.raw "$W"/windows.raw "$W"/raw.raw > "$W/before.sha256"
```

**1. Install onto a blank disk of each kind** (repeat with `KIND=virtio`, `nvme`, `sata`; each
kind has its own run directory, ephemeral keys and enrollment volume). The foreign disks are
attached in every run, plus the enrollment volume, so the installer sees six disks: the ISO, the
enrollment volume, three foreign disks and the target. `truncate` makes the sparse target.

```sh
KIND=virtio                                      # or nvme, or sata
R=$W/$KIND; mkdir -m700 "$R"; cp /usr/share/OVMF/OVMF_VARS_4M.fd "$R/OVMF_VARS.fd"
python3 tup/boot/tests-runtime/remote_check.py prepare --output "$R" --port "$PORT"   # keys, "$R/remote/enroll.img",
                                                                                      # "$R/remote/enroll/authorized_keys"
sha256sum "$R/remote/enroll.img" >> "$W/before.sha256"
truncate -s 24G "$R/target.raw"
case $KIND in
  virtio) T=(-device virtio-blk-pci,drive=target,serial=TUPVIRTIO0001) ;;
  nvme)   T=(-device nvme,drive=target,serial=TUPNVME0001) ;;
  sata)   T=(-device ide-hd,drive=target,bus=ide.1,serial=TUPSATA0001) ;;
esac
qemu-system-x86_64 -machine pc-q35-8.2,accel=tcg -cpu max -m 2048 -smp 2 -nodefaults -device VGA \
  -display none -monitor none -no-reboot -serial "file:$R/serial-install.log" \
  -drive if=pflash,format=raw,readonly=on,file=$OVMF -drive if=pflash,format=raw,file="$R/OVMF_VARS.fd" \
  -netdev user,id=net0,ipv6=off,restrict=on,hostfwd=tcp:127.0.0.1:$PORT-10.0.2.15:22 \
  -device virtio-net-pci,netdev=net0,romfile= -qmp "unix:$R/qmp.sock,server=on,wait=off" \
  -drive if=none,id=iso,format=raw,media=cdrom,readonly=on,file="$TUP_ISO" -device ide-cd,drive=iso,bootindex=1 \
  -drive if=none,id=enroll,format=raw,readonly=on,file="$R/remote/enroll.img" -device virtio-blk-pci,drive=enroll \
  -drive if=none,id=foreign,format=raw,file="$W/foreign.raw" -device virtio-blk-pci,drive=foreign,serial=FOREIGN0001 \
  -drive if=none,id=windows,format=raw,file="$W/windows.raw" -device virtio-blk-pci,drive=windows,serial=WINDOWS0001 \
  -drive if=none,id=rawdisk,format=raw,file="$W/raw.raw" -device virtio-blk-pci,drive=rawdisk,serial=RAWDISK0001 \
  -drive if=none,id=target,format=raw,file="$R/target.raw" "${T[@]}" &
```

Wait for the live system's owner login (the enrollment volume enrolls the key of `$R/remote/owner_key`),
then copy the same public key in as the install-time enrollment input and run the installer in the guest.
Find the target by serial, never by name. The input also carries a `clock` file and a stray
`.DS_Store`, to see the ignored name in the summary:

```sh
SSHO=(-F none -i "$R/remote/owner_key" -o IdentitiesOnly=yes -o UserKnownHostsFile="$R/known_hosts.install"
      -o StrictHostKeyChecking=accept-new)
ssh "${SSHO[@]}" -p $PORT owner@127.0.0.1 'mkdir -p enroll-in && echo utc > enroll-in/clock && : > enroll-in/.DS_Store'
scp "${SSHO[@]}" -P $PORT "$R/remote/enroll/authorized_keys" owner@127.0.0.1:enroll-in/
ssh "${SSHO[@]}" -p $PORT owner@127.0.0.1                    # interactive; or pass the commands below
sudo lsblk -dno PATH,SERIAL,SIZE,TRAN                        # check the six disks
SERIAL=TUPVIRTIO0001                                         # TUPNVME0001 / TUPSATA0001
DISK=$(lsblk -dno PATH,SERIAL | awk -v s=$SERIAL '$2==s{print $1}')
sudo tup-install plan --target "$DISK" --source /run/rootfsbase --output /root/plan.json \
    --enroll-input "$PWD/enroll-in" --state /root/install-state-1 | tee plan.txt
TOKEN=$(sed -n 's/^Confirmation token: //p' plan.txt)
sudo tup-install apply --plan /root/plan.json --confirm "$TOKEN" --state /root/install-state-1
sudo findmnt -R /root/install-state-1 || echo "no mounts left"
sudo cat /root/install-state-1/RECEIPT.json
```

Pass: the summary shows the planned serial, `disks in use ... sr0` (never the target), the
enrollment account, scope and key fingerprint, `ignored, not copied (macOS metadata): .DS_Store`, and a
`state ... is on VOLATILE storage (tmpfs)` line; apply exits 0, the receipt lists
`/dev/vdXN`, `/dev/nvme0n1p1`/`p2` or `/dev/sdXN` nodes read from sysfs, and no mount remains.
Power off from the guest (`sudo systemctl poweroff`), then on the host:

```sh
sha256sum --check --strict "$W/before.sha256"               # foreign disks and enrollment images unchanged
sfdisk --json "$R/target.raw"                               # same GUIDs, starts, sizes as RECEIPT.json
e2fsck -fn "$R/target.raw?offset=$((1050624*512))"          # root; use its start sector from the receipt
mdir -i "$R/target.raw@@$((2048*512))" ::EFI/BOOT ::tup     # ESP files
```

**2. Boot the installed disk with the ISO removed.** For virtio the existing scenario boots a
copy-on-write view of the image (`snapshot=on`) and judges the serial log with `boot_verdict.sh`:
`bash tup/boot/tests-runtime/uefi.sh installed-disk "$R/target.raw" "$(sha256sum "$R/target.raw" | cut -d' ' -f1)" "$W/boot-virtio"`.
It has no network, so it proves only `tup login:` on `ttyS0`. For the SSH proof and for
NVMe and SATA, boot manually with the same machine arguments but neither the ISO nor the
enrollment volume, the target first in boot order and `snapshot=on` (the first boot writes the
machine ID and SSH host keys), then run the SSH checks with the key that was enrolled at install
time:

```sh
qemu-system-x86_64 -machine pc-q35-8.2,accel=tcg -cpu max -m 2048 -smp 2 -nodefaults -device VGA \
  -display none -monitor none -no-reboot -serial "file:$R/serial-boot.log" \
  -drive if=pflash,format=raw,readonly=on,file=$OVMF -drive if=pflash,format=raw,file="$R/OVMF_VARS.fd" \
  -netdev user,id=net0,ipv6=off,restrict=on,hostfwd=tcp:127.0.0.1:$PORT-10.0.2.15:22 \
  -device virtio-net-pci,netdev=net0,romfile= -qmp "unix:$R/qmp.sock,server=on,wait=off" \
  -drive if=none,id=target,format=raw,snapshot=on,file="$R/target.raw" "${T[@]/serial=/bootindex=1,serial=}" &
python3 tup/boot/tests-runtime/remote_check.py verify --output "$R" --port $PORT --owner owner --wait 300
```

Pass: `tup login:` in the serial log, `RESULT` checks `owner_key_login`, `guest_system_running`
and the rest of `remote_check.py`'s list pass without the stick or enrollment volume;
`/proc/cmdline` shows `root=PARTUUID=<root GUID from the receipt> rootwait ro systemd.gpt_auto=0`
and, because GRUB chose the entry for QEMU, ends `console=tty0 console=ttyS0,115200n8
systemd.log_target=console` (the GRUB menu text is in the serial log: both entries, no rescue
entry); `findmnt /boot/efi` shows the ESP by UUID **exactly once** and `findmnt -R /` shows no
second mount of that partition (gpt-auto is off); `ls /boot` still shows the kernel files;
`cat /etc/tup/hardware-clock-utc` exists because the `clock` file said `utc` (and
`systemctl status systemd-timesyncd` is not condition-skipped); `dmesg | grep -i microcode`
shows the early update (TCG with `-cpu max` may not be an AMD CPU; on that VM the line is "not
applicable", record it), `cat /etc/machine-id` is non-empty and differs between two installs,
`ls /etc/ssh/ssh_host_*` shows keys generated at that boot. Also boot once on the machine
type's default entry by forcing a manufacturer other than `QEMU`
(`-smbios type=1,manufacturer=TUP`): the screen entry is chosen and the serial log still shows
GRUB's menu.

**3. Wrong target, Windows-looking target, token mismatch, `--allow-existing`.** In a live session as above:

```sh
FOREIGN=$(lsblk -dno PATH,SERIAL | awk '$2=="FOREIGN0001"{print $1}')
WINDOWS=$(lsblk -dno PATH,SERIAL | awk '$2=="WINDOWS0001"{print $1}')
RAWDISK=$(lsblk -dno PATH,SERIAL | awk '$2=="RAWDISK0001"{print $1}')
sudo tup-install plan --target "$FOREIGN" --source /run/rootfsbase --output /root/p-foreign.json   # REFUSED: already holds data
sudo tup-install plan --target "$WINDOWS" --source /run/rootfsbase --output /root/p-win.json       # REFUSED: looks like Windows
sudo tup-install plan --target "$WINDOWS" --source /run/rootfsbase --output /root/p-win.json --allow-existing   # still REFUSED
sudo tup-install plan --target "$RAWDISK" --source /run/rootfsbase --output /root/p-raw.json       # REFUSED: unrecognised non-zero data in the head
sudo tup-install plan --target "$RAWDISK" --source /run/rootfsbase --output /root/p-raw.json --allow-existing   # accepted, and the summary lists that data
sudo tup-install plan --target /dev/disk/by-id/anything --source /run/rootfsbase --output /root/x.json   # REFUSED: by-id
sudo tup-install plan --target "${DISK}1" --source /run/rootfsbase --output /root/x.json                # REFUSED: not a whole disk (nvme: ${DISK}p1)
sudo tup-install plan --target /dev/sr0 --source /run/rootfsbase --output /root/x.json                  # REFUSED: optical/boot medium
sudo tup-install plan --target "$FOREIGN" --source /run/rootfsbase --output /root/p-foreign2.json --allow-existing | tee pf.txt
FTOKEN=$(sed -n 's/^Confirmation token: //p' pf.txt)      # a valid token, for the other disk
sudo tup-install apply --plan /root/plan.json --confirm "WRONG-00000000" --state /root/s-wrong       # REFUSED: token
sudo tup-install apply --plan /root/plan.json --confirm "$FTOKEN" --state /root/s-wrong2            # REFUSED: token of the other disk
```

Pass: every refusal exits 2 with the stated reason, `s-wrong*` is not created, and on the host
`sha256sum --check --strict "$W/before.sha256"` still passes after power-off. Never run `apply` on
`p-foreign2.json`. Repeat the whole sequence booted from the Ventoy image
(`ventoy-image.py` then the `ventoy-tup-ssh` machine arguments of `uefi.sh`: Ventoy image as
`usb-storage` on `qemu-xhci`): `plan --target` the stick's disk (`/dev/sdX`, the one with `VTOYEFI`)
must be refused with "in use by this system" naming `.../tup-ventoy/media`, even with `--allow-existing`
(the in-use check comes before the Windows refusal; the stick's data partition is exFAT, which would
be refused as Windows-looking too). Drift: make a good plan of
the blank target, then in the same guest put a filesystem on the disposable target
(`sudo mkfs.ext4 -q -F "$DISK"`) and run `apply` with the plan's token: it must refuse with
"differs from the plan (... filesystem signatures)" and `/root/install-state-*` must not exist.
Repeat after `sudo mount "$DISK" /mnt` (new mount): refused as in use / differs.

**4. Kill the installer mid-copy.**

```sh
sudo sh -c "tup-install apply --plan /root/plan.json --confirm '$TOKEN' --state /root/install-state-2 \
    > /root/apply-2.log 2>&1 &"
until sudo grep -q '"step": "copy-root"' /root/install-state-2/PROGRESS.jsonl 2>/dev/null; do sleep 1; done
sudo kill -TERM "$(pgrep -f '^/usr/bin/python3 -I -B .*/disk.py apply')"   # catchable: waits for cp, then INTERRUPTED and no mounts
sleep 5; sudo findmnt -R /root/install-state-2 || echo "no mounts left"; sudo cat /root/apply-2.log
sudo ls /root/install-state-2; sudo cat /root/install-state-2/FAILED.json
sudo tup-install apply --plan /root/plan.json --confirm "$TOKEN" --state /root/install-state-2    # REFUSED: exists, prints intent, last step copy-root
sudo tup-install apply --plan /root/plan.json --confirm "$TOKEN" --state /root/install-state-3    # REFUSED: differs from the plan (partition table)
sudo tup-install plan --target "$DISK" --source /run/rootfsbase --output /root/plan2.json --allow-existing   # lists the partitions left
```

Pass: the log ends `INTERRUPTED (signal 15)` (after `cp` finished: the installer waits for its
detached child), no mount, `FAILED.json` step `copy-root`, both reruns refused with the reasons in
the comments, the new plan lists `TUP-ESP`/`TUP-ROOT` as to be erased, and applying that plan
succeeds and boots as in scenario 2. Then repeat with a hard kill of QEMU instead of
`pkill` (`kill -9` of the `qemu-system-x86_64` process, which also destroys the RAM-resident state
directory): after rebooting the live ISO the same `apply --plan` with the old plan and a new
state directory must refuse as drift.

Each scenario's logs, the plan, the receipt and the `sha256sum` check belong in a new run
directory; a result file that cannot be explained should be kept, not rerun silently.

## Facts for the hurdle register (not edited here)

- **H10.** `disk.py` installs x86_64-efi GRUB as `EFI/BOOT/BOOTX64.EFI` built by `grub-mkstandalone`,
  a GPT with an ESP (type C12A7328-...) and an x86-64 root (4F68BCE3-...), kernel and AMD microcode
  cpio on the ESP, and never writes firmware variables. The i386-pc override at
  `overrides/x86_64/ch10/grub.sh` is not used. The menu follows the live ISO's console policy.
  Gate unmet: no firmware has started the result.
- **H11.** Nothing appends a digit to a device name; partition nodes come from sysfs after the table is
  written and are confirmed against sysfs again before each `mkfs`; the kernel root is
  `PARTUUID=<GPT partition GUID>`, fstab uses `UUID=`; no initramfs is involved. Unit tests cover virtio,
  NVMe `pN`, SATA and USB naming. Gate unmet: reordered-disk and physical SATA/NVMe boots.
- **H17.** Target identity is the full `lsblk` record plus table dump, every signature and a sample of
  the first and last MiB, bound into a plan digest and a token made of the serial or WWN and eight digest hex
  digits, and compared with the disk again immediately before the first write. Refusals for
  partitions, loop/dm/md/zram/rom, read-only, mounted, swapped-on, held, running-system, boot-medium,
  symlinked-name, existing-data, Windows-looking (no override) and drifted targets are tested with zero
  recorded write commands. Gate unmet: no real device, no real Ventoy chain, no check on the desktop.
- **H18.** Payload is the squashfs lower root copied with `cp -a --one-file-system` and verified by
  comparing complete `inventory()` of source, copy and final root (owners, modes, mtimes, xattrs including
  capabilities and ACLs, hardlinks, symlinks); intent record before the first write, receipt after
  verification and `sync`; interruptions are never resumed; mounts are released on every catchable exit.
  Gate unmet: no run on a mounted ext4 from a live system and no power-loss test; the owner's final exact-target
  confirmation is the token typed on the desktop.
