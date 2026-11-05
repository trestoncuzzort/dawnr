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
real `sfdisk`, `mkfs.ext4`, `mkfs.fat`, `blkid`, `cpio` and
`grub-script-check` on regular files. It has never touched a block device,
never run inside the live image and never booted an installed disk.** Section
"Not yet shown" lists what only a VM and then the desktop can show.

```sh
python3 /usr/lib/tup-installer/tup/install/disk.py plan  --target /dev/nvme0n1 --source /run/rootfsbase \
    --output /root/plan.json [--esp-mib 512] [--enroll-input DIR] [--allow-existing]
python3 /usr/lib/tup-installer/tup/install/disk.py apply --plan /root/plan.json \
    --confirm TOKEN --state /root/install-state-1
```

The install location, the `/usr/sbin` wrapper and the layer that ships these
files are the integrator's: this change adds nothing to the image layout. The
module imports `tup.boot.inputs`, so the installed tree must keep
`tup/install/disk.py`, `tup/boot/__init__.py` and `tup/boot/inputs.py` in the
same relative places under one directory (expected: `/usr/lib/tup-installer/`).
`plan` prints a summary that ends with `Confirmation token: SERIAL-XXXXXXXX`.

## What `plan` does and records

`plan` runs only commands whose exact shapes `read_only_command()` lists
(`lsblk --json --bytes -o ...`, `sfdisk --dump|--json`, `wipefs --no-act
--json`, `blkid -p -o export`, and version probes). A wrapper raises before
executing anything else, and the tests drive `plan` through a fake host in which
every write-capable tool would be recorded: none ever is.

It stores in `PLAN.json`: the whole-disk identity (kernel name, vendor, model,
serial, WWN, size in bytes, logical and physical sector size, transport,
removable, hotplug, read-only, partition-table type and every partition with its
filesystem facts), the `sfdisk --dump` text, every `wipefs` and `blkid` signature
of the disk and of each partition on it, and a digest of all of that; the disks in
use by this system; the source's mount, inventory digest, entry and byte counts;
the kernel release and image digest; the microcode decision; the enrollment
input's file digests; every identifier of the new disk (disk GUID, both partition
GUIDs, the FAT volume ID, the ext4 UUID); the exact `sfdisk` script, `fstab` and
`grub.cfg`; and the path, SHA256 and reported version of every tool. The plan's
digest covers all of it.

## What it refuses

Each case is a unit test with zero write commands recorded.

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
  A mount whose disk cannot be determined (for example a loop backing file that no
  longer resolves) refuses instead of being ignored.
- A source that is not exactly a read-only `squashfs` or `erofs` mount point, which
  also refuses `--source /` (the running overlay carries enrollment state and
  host keys), or that fails `check_offline_root` (machine ID, SSH host keys,
  locked root, `ID=tup`), already holds `etc/tup/owner-enrolled.json`, has no
  single `/boot/vmlinuz-RELEASE`, or whose kernel fails `check_kernel`.
- A disk that has a partition table, a partition, any `wipefs` signature or any
  `blkid` hit, unless `--allow-existing` is given; then `PLAN.json` and the summary
  list each of them in words under "this will ERASE". A Windows "RAW" report is
  not treated as emptiness.
- A disk with neither serial nor WWN (it could not be named in the token), one too
  small for the live root plus 15 % and 512 MiB, or `--esp-mib` outside 64-8192.

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
3. Re-measure the tools, then re-read the identity and the complete state and refuse
   on any difference (serial, WWN, size, sector size, table, any signature, mounts,
   holders), refuse on a wrong token, refuse if the set of disks in use changed,
   re-run every safety check, recompute the source inventory, kernel and
   microcode, the enrollment input and the installer's own digest.
4. `mkdir` the state directory (0700), write and fsync `INTENT.json`.
5. Build the boot files inside the state directory (`grub.cfg` checked with
   `grub-script-check`, `grub-mkstandalone` image, microcode cpio).
6. **First write to the disk:** `sfdisk --lock --wipe always --wipe-partitions
   always DISK` with the planned script on standard input; `udevadm settle`; the
   new partitions' device nodes are found from sysfs (partition number, start and
   size in 512-byte units must equal the plan, and the nodes must exist), never by
   appending a digit; `sfdisk --json` must show exactly the planned GUIDs, types,
   names, starts and sizes.
7. `mkfs.fat -F 32 -i VOLUMEID -n TUP-ESP`, `mkfs.ext4 -F -q -U UUID -L TUP-ROOT`,
   `udevadm settle`, then `blkid -p` must report the planned type, UUID and label.
8. Mount the root and the ESP below the state directory; each mount is checked against
   `/proc/self/mountinfo` for the right device number and filesystem.
9. `cp -a --one-file-system SOURCE/. ROOT/`. Then `inventory()` of the copy must equal
   the source inventory except that `lost+found` (made by `mke2fs`) exists.
10. Write `etc/fstab`; create `boot/efi` if missing; refuse if the copy holds a machine ID or SSH
    host keys; if an enrollment input was planned create `etc/tup` (0755) and
    `etc/tup/enroll-input` (0700) and write its files 0600, root-owned.
11. Write `EFI/BOOT/BOOTX64.EFI`, the kernel and `amd-ucode.img` on the ESP.
12. `inventory()` of the root again: the only paths allowed to differ from the source are
    `lost+found`, `etc`, `etc/fstab`, `boot`, `boot/efi` and the enrollment paths. The
    fstab and every ESP file are read back and compared.
13. `sync`, unmount (ESP then root), `e2fsck -f -n`, `fsck.fat -n`, `blkid -p` and
    `sfdisk --json` once more, `sync`.
14. Only now write `RECEIPT.json` (`tup.install-receipt.v1`): plan digest, target
    identity, every created identifier and device node, source, copy and deployed
    inventory digests, the digest of each boot file and of `grub.cfg`, tools with path,
    digest and version, timestamps, and `boot_tested: false`, `release_eligible: false`.

`PROGRESS.jsonl` (fsynced before each step) and `COMMANDS.jsonl` (argv, exit status,
bounded output) stay in the state directory. A failure writes `FAILED.json` naming the
step. Every mount `apply` made is unmounted on every exit path: failure, `SIGINT`,
`SIGTERM` and `SIGHUP` (converted to an exception), each mount attempted even if an
earlier unmount fails; if one cannot be unmounted the run says which, loudly, and
leaves it for the operator. `SIGKILL` or power loss cannot be handled; the mounts then
die with the live system.

**Interrupted runs are never resumed.** A second `apply` with the same state directory
refuses and prints the recorded intent. A second `apply` with the same plan and a new
state directory refuses because the disk no longer matches the plan (unless the run was
stopped before `sfdisk` wrote, in which case nothing was written and it may proceed).
Recovery is a new `plan --allow-existing`, which lists what the interrupted attempt left.
The state directory lives on the live system's RAM overlay; surviving a power cut is
not claimed, only that the disk drifts away from the plan.

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
3.87 MB, PE32+ x86-64 EFI application). The tradeoff is that changing the menu means
rebuilding `BOOTX64.EFI` with the same command. The target's GRUB is built for `x86_64-efi`
only (the audit entry omits the BIOS and i386-efi builds), which is exactly the platform
used.

**`grub.cfg`.** Written by `disk.py`: `search --fs-uuid` for the ESP, `linux
/tup/vmlinuz-RELEASE root=PARTUUID=<root GUID> rootwait ro console=tty0
console=ttyS0,115200n8`, `initrd /tup/amd-ucode.img`, timeout 3, and a second entry adding
`systemd.unit=rescue.target`. No serial or other input terminal is configured, so an absent
UART cannot inject keystrokes into the menu. The kernel is on the ESP, copied from
`/boot`, so GRUB reads only FAT32.

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

## Measured, and not

| Ran | Where | Result |
| --- | --- | --- |
| 40 unit tests in `tests/test_install_disk.py` | Linux builder, Python 3.12 | pass, 1 skip without a GRUB `grub-script-check` on `PATH`; with GRUB 2.14's tools on `PATH` all 3 real-tool tests pass |
| `sfdisk` (util-linux 2.39.3) applies the generated script to a regular file; `sfdisk --json` shows the planned GUIDs, offsets and sizes; the last partition ends on a 1 MiB boundary inside the usable range | builder, regular file | pass; 512 and 4096 byte sector layouts are computed (4096 only by arithmetic, not by `sfdisk`) |
| `mkfs.ext4 -U -L`, `mkfs.fat -F 32 -i -n` on 64 MiB files; `blkid -p` reports the planned UUID, volume ID and label; `e2fsck -fn`, `fsck.fat -n` accept | builder | pass |
| `grub-script-check` on the generated `grub.cfg`; `grub-mkstandalone` with the exact argv `apply` uses | builder, host-built GRUB 2.14 | pass; config found in the image |
| Real `lsblk --json --bytes -o ...` parsed by `read_identity`, real mount table and sysfs resolved by `disks_in_use` | builder (WSL), read-only | parsed; resolved `/` to its disk; its overlay `lowerdir` path did not exist in this namespace and so correctly refused |

Not run: any write to a `/dev` node, a loop device, a mount of what the installer made, QEMU,
Ventoy, the installed system booting, `tup-enroll.service` reading the new input directory,
and the installer inside the TUP image.

## Not yet shown (what only a VM and then the desktop can show)

- That `/run/rootfsbase` in the booted live image is a read-only `squashfs` mount point, that
  `disks_in_use` resolves the real Ventoy chain (loop `backing_file` paths as the kernel
  prints them after `switch_root`) and the plan names the stick as in use.
- That the ISO's squashfs lower root passes `check_offline_root` and `check_kernel` as booted.
- That `sfdisk`, `udevadm settle` and the kernel produce `/dev/vdXN`, `/dev/nvme0n1pN` and
  `/dev/sdXN` in time (thirty one-second polls) and that `wipefs`/`blkid` read-only probes
  behave on real devices.
- That `mount -t vfat -o umask=0077,codepage=437,iocharset=iso8859-1` and the `fsck.fat -n`
  / `e2fsck -fn` pass on what `mkfs` made, and that the full copy completes in the live
  system's RAM and time limits.
- That firmware starts `EFI/BOOT/BOOTX64.EFI`, the menu appears, GRUB's `linux` loads the
  kernel from FAT, the kernel mounts `root=PARTUUID=` without an initramfs, and the early
  microcode is applied (`dmesg` shows `microcode: ... updated early`).
- That `systemd` runs correctly from the copied root: no live-only units misbehave, an empty
  `/etc/machine-id` is committed on the first boot, `tup-enroll.service` finds
  `etc/tup/enroll-input` (the integrator adds that search location) and SSH comes up with the
  USB stick removed; and that `rescue.target` is reachable (with a locked root account
  `sulogin` will not open a shell; this is expected and untested).
- Windows on the SATA SSD is not touched: only a run of the plan on the real machine, with the
  NVMe selected by its serial, can show the Windows disk is listed as in use or unrelated
  and that nothing on it changes.

## VM test plan for the integrator

Not run. It uses `tup/boot/tests-runtime`'s real options (`uefi.sh`, `remote_check.py`) from the
unmerged runtime branch: QEMU 8.2, `-machine pc-q35-8.2,accel=tcg -cpu max`, `-nodefaults`, OVMF
4M code and a private copy of the variables, one user-mode network with `restrict=on` and a
single loopback forward, `-serial file:`. `uefi.sh` only runs fixed scenarios, so the install
scenarios below launch QEMU with the same arguments. Run as root on the Linux test host, one QEMU
at a time.

```sh
export TUP_ISO=...   TUP_ISO_SHA256=...        # the ISO that contains /usr/lib/tup-installer
export W=$TUP_VM_RUNS/install-01  PORT=2224    # W must not exist
mkdir -m700 "$W" && cp /usr/share/OVMF/OVMF_VARS_4M.fd "$W/OVMF_VARS.fd"
OVMF=/usr/share/OVMF/OVMF_CODE_4M.fd
```

**0. Fixtures.** A foreign disk that must never change:

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
sha256sum "$W/foreign.raw" > "$W/before.sha256"
```

**1. Install onto a blank disk of each kind** (repeat with `KIND=virtio`, `nvme`, `sata`; each
kind has its own run directory, ephemeral keys and enrollment volume). The foreign disk is attached in
every run, plus the enrollment volume, so the installer sees four disks: the ISO, the enrollment
volume, the foreign disk and the target. `truncate` makes the sparse target.

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
  -device virtio-net-pci,netdev=net0,romfile= \
  -drive if=none,id=iso,format=raw,media=cdrom,readonly=on,file="$TUP_ISO" -device ide-cd,drive=iso,bootindex=1 \
  -drive if=none,id=enroll,format=raw,readonly=on,file="$R/remote/enroll.img" -device virtio-blk-pci,drive=enroll \
  -drive if=none,id=foreign,format=raw,file="$W/foreign.raw" -device virtio-blk-pci,drive=foreign,serial=FOREIGN0001 \
  -drive if=none,id=target,format=raw,file="$R/target.raw" "${T[@]}" &
```

Wait for the live system's owner login (the enrollment volume enrolls the key of `$R/remote/owner_key`),
then copy the same public key in as the install-time enrollment input and run the installer in the guest.
Find the target by serial, never by name:

```sh
SSHO=(-F none -i "$R/remote/owner_key" -o IdentitiesOnly=yes -o UserKnownHostsFile="$R/known_hosts.install"
      -o StrictHostKeyChecking=accept-new)
ssh "${SSHO[@]}" -p $PORT owner@127.0.0.1 'mkdir -p enroll-in'
scp "${SSHO[@]}" -P $PORT "$R/remote/enroll/authorized_keys" owner@127.0.0.1:enroll-in/
ssh "${SSHO[@]}" -p $PORT owner@127.0.0.1                    # interactive; or pass the commands below
sudo lsblk -dno PATH,SERIAL,SIZE,TRAN                        # check the four disks
SERIAL=TUPVIRTIO0001                                         # TUPNVME0001 / TUPSATA0001
DISK=$(lsblk -dno PATH,SERIAL | awk -v s=$SERIAL '$2==s{print $1}')
D=/usr/lib/tup-installer/tup/install/disk.py
sudo python3 $D plan --target "$DISK" --source /run/rootfsbase --output /root/plan.json \
    --enroll-input "$PWD/enroll-in" | tee plan.txt
TOKEN=$(sed -n 's/^Confirmation token: //p' plan.txt)
sudo python3 $D apply --plan /root/plan.json --confirm "$TOKEN" --state /root/install-state-1
sudo findmnt -R /root/install-state-1 || echo "no mounts left"
sudo cat /root/install-state-1/RECEIPT.json
```

Pass: the summary shows the planned serial and `disks in use ... sr0` (never the target), apply exits 0,
the receipt lists `/dev/vdXN`, `/dev/nvme0n1p1`/`p2` or `/dev/sdXN` nodes read from sysfs, and no mount
remains. Power off from the guest (`sudo systemctl poweroff`), then on the host:

```sh
sha256sum --check --strict "$W/before.sha256"               # foreign disk and enrollment images unchanged
sfdisk --json "$R/target.raw"                               # same GUIDs, starts, sizes as RECEIPT.json
e2fsck -fn "$R/target.raw?offset=$((1050624*512))"          # root; use its start sector from the receipt
mdir -i "$R/target.raw@@$((2048*512))" ::EFI/BOOT ::tup     # ESP files
```

**2. Boot the installed disk with the ISO removed.** For virtio the existing scenario boots a
copy-on-write view of the image (`snapshot=on`) and judges the serial log with `boot_verdict.sh`:
`bash tup/boot/tests-runtime/uefi.sh installed-disk "$W/virtio/target.raw" "$(sha256sum "$W/virtio/target.raw" | cut -d' ' -f1)" "$W/boot-virtio"`.
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
and the rest of `remote_check.py`'s list pass without the stick or enrollment volume, `/proc/cmdline`
shows `root=PARTUUID=<root GUID from the receipt> ... console=ttyS0,115200n8`, `dmesg | grep -i microcode`
shows the early update (TCG with `-cpu max` may not be an AMD CPU; on that VM the line is "not
applicable", record it), `cat /etc/machine-id` is non-empty and differs between two installs,
`ls /etc/ssh/ssh_host_*` shows keys generated at that boot, and `findmnt /boot/efi` is the ESP by UUID.
The `rescue.target` entry: choose it from the GRUB menu (QMP `send-key`), expect the sulogin refusal
message for a locked root, and a clean reboot.

**3. Wrong target, token mismatch, `--allow-existing`.** In a live session as above:

```sh
FOREIGN=$(lsblk -dno PATH,SERIAL | awk '$2=="FOREIGN0001"{print $1}')
sudo python3 $D plan --target "$FOREIGN" --source /run/rootfsbase --output /root/p-foreign.json   # REFUSED: already holds data
sudo python3 $D plan --target /dev/disk/by-id/anything --source /run/rootfsbase --output /root/x.json   # REFUSED: by-id
sudo python3 $D plan --target "${DISK}1" --source /run/rootfsbase --output /root/x.json                # REFUSED: not a whole disk (nvme: ${DISK}p1)
sudo python3 $D plan --target /dev/sr0 --source /run/rootfsbase --output /root/x.json                  # REFUSED: optical/boot medium
sudo python3 $D plan --target "$FOREIGN" --source /run/rootfsbase --output /root/p-foreign2.json --allow-existing | tee pf.txt
FTOKEN=$(sed -n 's/^Confirmation token: //p' pf.txt)      # a valid token, for the other disk
sudo python3 $D apply --plan /root/plan.json --confirm "WRONG-00000000" --state /root/s-wrong       # REFUSED: token
sudo python3 $D apply --plan /root/plan.json --confirm "$FTOKEN" --state /root/s-wrong2            # REFUSED: token of the other disk
```

Pass: every refusal exits 2 with the stated reason, `s-wrong*` is not created, and on the host
`sha256sum --check --strict "$W/before.sha256"` still passes after power-off. Never run `apply` on
`p-foreign2.json`. Repeat the whole sequence booted from the Ventoy image
(`ventoy-image.py` then the `ventoy-tup-ssh` machine arguments of `uefi.sh`: Ventoy image as
`usb-storage` on `qemu-xhci`): `plan --target` the stick's disk (`/dev/sdX`, the one with `VTOYEFI`)
must be refused with "in use by this system" naming `.../tup-ventoy/media`, even with `--allow-existing`.
Drift: make a good plan of the blank target, then in the same guest put a filesystem on the
disposable target (`sudo mkfs.ext4 -q -F "$DISK"`) and run `apply` with the plan's token: it must refuse
with "differs from the plan (... filesystem signatures)" and `/root/install-state-*` must not exist.
Repeat after `sudo mount "$DISK" /mnt` (new mount): refused as in use / differs.

**4. Kill the installer mid-copy.**

```sh
sudo sh -c "python3 $D apply --plan /root/plan.json --confirm '$TOKEN' --state /root/install-state-2 \
    > /root/apply-2.log 2>&1 &"
until sudo grep -q '"step": "copy-root"' /root/install-state-2/PROGRESS.jsonl 2>/dev/null; do sleep 1; done
sudo kill -TERM "$(pgrep -f '^python3 .*/disk.py apply')"   # catchable: expect INTERRUPTED and no mounts
sleep 5; sudo findmnt -R /root/install-state-2 || echo "no mounts left"; sudo cat /root/apply-2.log
sudo ls /root/install-state-2; sudo cat /root/install-state-2/FAILED.json
sudo python3 $D apply --plan /root/plan.json --confirm "$TOKEN" --state /root/install-state-2    # REFUSED: exists, prints intent, last step copy-root
sudo python3 $D apply --plan /root/plan.json --confirm "$TOKEN" --state /root/install-state-3    # REFUSED: differs from the plan (partition table)
sudo python3 $D plan --target "$DISK" --source /run/rootfsbase --output /root/plan2.json --allow-existing   # lists the partitions left
```

Pass: the log ends `INTERRUPTED (signal 15)`, no mount, `FAILED.json` step `copy-root`, both reruns refused with the
reasons in the comments, the new plan lists `TUP-ESP`/`TUP-ROOT` as to be erased, and applying that
plan succeeds and boots as in scenario 2. Then repeat with a hard kill of QEMU instead of
`pkill` (`kill -9` of the `qemu-system-x86_64` process, which also destroys the RAM-resident state
directory): after rebooting the live ISO the same `apply --plan` with the old plan and a new
state directory must refuse as drift.

Each scenario's logs, the plan, the receipt and the `sha256sum` check belong in a new run
directory; a result file that cannot be explained should be kept, not rerun silently.

## Facts for the hurdle register (not edited here)

- **H10.** `disk.py` installs x86_64-efi GRUB as `EFI/BOOT/BOOTX64.EFI` built by `grub-mkstandalone`,
  a GPT with an ESP (type C12A7328-...) and an x86-64 root (4F68BCE3-...), kernel and AMD microcode
  cpio on the ESP, and never writes firmware variables. The i386-pc override at
  `overrides/x86_64/ch10/grub.sh` is not used. Gate unmet: no firmware has started the result.
- **H11.** Nothing appends a digit to a device name; partition nodes come from sysfs after the table is
  written; the kernel root is `PARTUUID=<GPT partition GUID>`, fstab uses `UUID=`; no initramfs is
  involved. Unit tests cover virtio, NVMe `pN`, SATA and USB naming. Gate unmet: reordered-disk and
  physical SATA/NVMe boots.
- **H17.** Target identity is the full `lsblk` record plus table dump and every signature, bound into
  a plan digest and a token made of the serial or WWN and eight digest hex digits. Refusals for
  partitions, loop/dm/md/zram/rom, read-only, mounted, swapped-on, held, running-system, boot-medium,
  symlinked-name, existing-data and drifted targets are tested with zero recorded write commands. Gate
  unmet: no real device, no real Ventoy chain, no check on the desktop.
- **H18.** Payload is the squashfs lower root copied with `cp -a --one-file-system` and verified by
  comparing complete `inventory()` of source, copy and final root (owners, modes, mtimes, xattrs including
  capabilities and ACLs, hardlinks, symlinks); intent record before the first write, receipt after
  verification and `sync`; interruptions are never resumed; mounts are released on every catchable exit.
  Gate unmet: no run on a mounted ext4 from a live system and no power-loss test; the owner's final exact-target
  confirmation is the token typed on the desktop.
