# Native UEFI test artifacts

This layer packages an explicitly supplied, offline x86_64 TUP export into a
**direct-UEFI test ISO**. Its executable entrypoint is `assemble.py`. It has not
built or booted a real TUP image yet. The installed system, installer, a real
boot through Ventoy, networking and hardware qualification remain separate gates.

The pipeline is:

1. Recheck pinned host tools, the exported root inventory, kernel header/config,
   matching module tree and the boot-layer receipt.
2. Run native `validate --through ch08 --profile lfs-13.1-systemd` against the
   original core workspace. Require a newly rewritten, matching
   `state/CORE-COMPLETION.json`; an old marker or zero exit alone is insufficient.
3. Package the export with `mksquashfs`, using the stated CPU/memory budget.
4. Run host dracut 112 with an explicit TUP `--sysroot`, host framework path,
   clean configuration/environment, and no host-only root configuration. The
   initramfs uses dracut's own `/init`, not systemd (see below), and starts with
   the export's AMD family 19h microcode as an uncompressed early cpio.
5. Embed the SquashFS digest, its pre-pivot verification hook and the Ventoy
   live-root hook. Inspect the resulting initramfs for each of them, for the
   required live modules, for dracut's own live scripts and for early microcode
   whose bytes equal the staged container.
6. Use matching host GRUB 2.14 x86_64-efi modules and `grub-mkrescue`, then inspect
   the ISO's UEFI El Torito entry with xorriso. Flush the staged output and publish
   it into a fresh directory. Failed work retains diagnostics but no
   `ARTIFACT.json` completion receipt.

It never runs `grub-install`, `efibootmgr`, a partitioning program, or a mount
command. It has no block-device output argument. Packaging runs trusted build
tools in disposable Linux infrastructure; it is not a sandbox against malicious
tools or concurrent privileged modification. Keep inputs quiescent. The pre/post
inventories detect ordinary changes, not an attacker who changes and restores
inputs between observations.

`ARTIFACT.json` always says `packaged-unbooted`, `release_eligible: false`, and
records false boot/Ventoy claims: `ventoy_tested` stays false and the
`ventoy-unqualified` gate stays, although the ISO now carries a `ventoy.dat`
marker and a discovery hook. It preserves the core's source purpose,
eligibility, advisory review and release gates, including any H55 deferral.
There is no production release path. Deterministic configuration is not evidence
that two generated images are byte-identical.

## Dependency boundary

The 94-source LFS core lock is unchanged. These dependencies need separate
authenticated source/package records and build receipts before a real run:

| Location | Component | Contract |
| --- | --- | --- |
| TUP export | Linux 6.18.60, `-tup` local version | Reuse the selected authenticated kernel source; compile the native fragment below and retain config, image and modules together. |
| TUP export | LVM2 2.03.42 and libaio 0.3.113 | BLFS build supplying `/usr/sbin/dmsetup` and its libraries. Dracut's live module depends on device mapper even when using an OverlayFS root. Do not enable LVM services just to obtain dmsetup. |
| TUP export | systemd 261, udev, Bash, kmod, coreutils, util-linux and libraries | Come from the validated LFS 13.1 core. Dracut copies these target binaries from the export; host binaries must not substitute for them. |
| TUP export | `usr/lib/firmware/amd-ucode/microcode_amd_fam19h.bin` | The authenticated linux-firmware selection of `../hardware`. It must be the only file in `amd-ucode`, with no `intel-ucode` beside it, and `MICROCODE=y`, `CPU_SUP_AMD=y` in the kernel configuration; anything else refuses at `inspect`. |
| Build host only | dracut-ng 112, compiled helpers, module/config tree | Verified source/build. `dracutbasedir` explicitly selects the hashed host framework; `--sysroot` supplies target files. Target dracut is not needed for this ISO operation. |
| Build host only | GRUB 2.14, x86_64-efi modules | Build together from the authenticated GRUB source. Ubuntu's different GRUB version must not consume TUP's 2.14 modules. |
| Build host only | squashfs-tools 4.7.5, xorriso, mtools | Verified sources or authenticated distribution packages. Zstd and xattr support are required in mksquashfs. |
| Build host only | Bash, coreutils, findutils, awk, grep, sed, gzip, cpio, kmod, pkg-config, ldconfig and their libraries | Record the authenticated host package inventory and all relevant support trees in the host-tool review. A hash of a newly downloaded file is not source authentication. |
| Test host only | UEFI firmware and external x86_64 VM runner | Pin firmware/runner separately; record accelerator, device models and resource limits. Neither is installed in TUP or required by native boot. |

The host tool lock pins actual command files and support trees, not just version
strings. Its caller supplies a separately reviewed expected lock SHA256.
`provenance` points to verification evidence; the string itself is not a
signature verifier. Runtime libraries and helper programs still belong in that
host environment review. This is not a hermetic-build claim.

The executable, offline host builder is `host_tools.py`; [HOST-TOOLS.md](HOST-TOOLS.md)
records its authentication, build and qualification procedure. It reuses the
source verifier, stages every upstream install, pins the resulting prefix and
tests the real SquashFS/GRUB tools. Dracut's systemd unit, shell-completion and
pkg-config directories are explicitly kept under the private prefix. Rust cpio
is disabled to avoid an unpinned Cargo dependency. This host-only operation
does not install dracut or GRUB services into the preparation host or TUP.

Target build steps after the completed core and separate source gates pass:

- Target libaio and LVM2: follow the matching BLFS recipes in an isolated layer
  build based on the completed core. For LVM2 use the documented
  `./configure --prefix=/usr --enable-cmdlib --enable-pkgconfig --enable-udev_sync`
  and bounded `make -j4`, then install into the TUP layer environment. Its device
  regression suite is a separate disposable-device test; do not run it on the
  desktop's disks or record it as passed merely because dmsetup built.

`target-sources.json` retains separately authenticated libaio/LVM2 inputs.
Their target builds, device regression tests and layer orchestration/export
receipts remain unrun. No tool installation runs on import or during the
fixture suite.

## Kernel preparation

`kernel.py fragment` emits the initial native boot floor. It includes EFI/GPT,
initramfs, AHCI/NVMe/USB and virtio storage, ISO/SquashFS/OverlayFS, serial console
and systemd's documented basic requirements. It extends `x86_64_defconfig`; it
is not a complete native GPU/Wi-Fi, isolation, firmware or hardening profile.
The current fragment compiles these boot drivers in to avoid relying on a
preparation-host hardware scan. Actual 6.18.60 configuration/build is still unrun.

Use the authenticated 6.18.60 source and a fresh out-of-tree build directory.
The variables below must name the isolated source/build/export directories;
`TUP_EXPORT` is a directory, never a disk or the host `/`.

```sh
python3 tup/boot/kernel.py fragment > "$TUP_KERNEL_BUILD_FRAGMENT"
make -C "$TUP_KERNEL_SOURCE" O="$TUP_KERNEL_BUILD" ARCH=x86_64 x86_64_defconfig
"$TUP_KERNEL_SOURCE/scripts/kconfig/merge_config.sh" -m -O "$TUP_KERNEL_BUILD" \
  "$TUP_KERNEL_BUILD/.config" "$TUP_KERNEL_BUILD_FRAGMENT"
make -C "$TUP_KERNEL_SOURCE" O="$TUP_KERNEL_BUILD" ARCH=x86_64 olddefconfig
python3 tup/boot/kernel.py check --config "$TUP_KERNEL_BUILD/.config"
test "$(make -s -C "$TUP_KERNEL_SOURCE" O="$TUP_KERNEL_BUILD" kernelrelease)" = 6.18.60-tup
make -C "$TUP_KERNEL_SOURCE" O="$TUP_KERNEL_BUILD" ARCH=x86_64 -j4 bzImage modules
make -C "$TUP_KERNEL_SOURCE" O="$TUP_KERNEL_BUILD" ARCH=x86_64 \
  INSTALL_MOD_PATH="$TUP_EXPORT" modules_install
install -m644 "$TUP_KERNEL_BUILD/arch/x86/boot/bzImage" "$TUP_EXPORT/boot/vmlinuz-6.18.60-tup"
install -m644 "$TUP_KERNEL_BUILD/.config" "$TUP_EXPORT/boot/config-6.18.60-tup"
install -m644 "$TUP_KERNEL_BUILD/System.map" "$TUP_EXPORT/boot/System.map-6.18.60-tup"
```

Run this sequence with checked exit status (`set -euo pipefail`) and retained
logs in the disposable layer builder. After `olddefconfig`, a lost required
symbol must fail; do not weaken the check to hide an unsupported option. The
packager additionally reads the x86 boot header's architecture/protocol/release
and requires the matching module metadata directory. It hashes module bytes;
module vermagic/runtime loading still needs actual kernel/build/boot evidence.

## Export and input contracts

Export from the original completed core without mutating its build/receipt
workspace. Preserve modes, numeric owners, hardlinks, symlinks and xattrs. Apply
the separately receipted boot/network/access layers only to the export. Do not
copy build trees or live mounts. The packager requires empty/absent `sources`,
`tools`, `tup-build`, `dev`, `proc`, `sys`, `run` and `tmp`; it never silently
excludes populated directories. Maintain correct empty-directory modes, including
1777 for `/tmp`. Supply a regular `/etc/os-release` with `ID=tup` and an explicit
`VERSION_ID` for the receipted export. Use an empty/comment-only live `fstab`, an empty machine ID, no
SSH host private keys, and a locked root account. Owner keys/network credentials
are explicit private provisioning inputs managed by the remote layer.

A `tup.boot-layer.v1` receipt lives **outside** the root and contains:

```json
{
  "schema": "tup.boot-layer.v1",
  "architecture": "x86_64",
  "status": "complete",
  "core_inputs_sha256": "<original BUILD-INPUTS.json SHA256>",
  "source_lock_sha256": "<separate boot-layer source lock SHA256>",
  "recipe_sha256": "<receipted layer recipe identity>",
  "root_tree_sha256": "<sha256(canonical(inventory(export)))>"
}
```

Create it only after successful layer operations and checks; it is not a way to
turn unknown files into authenticated inputs. `tup.boot.inputs.inventory()`
returns the full tree inventory, and `tree_hash()` gives the specified identity.
The artifact retains that exact inventory as `ROOT-INVENTORY.json` and a separate
`MODULES-INVENTORY.json`. Ownership, mode, mtime, xattrs and hardlink grouping
are included. Only files, directories and symlinks are supported; device nodes,
sockets, FIFOs and nested filesystems refuse.

The external core-validator JSON has schema `tup.boot-core-validator.v1`,
`script` (absolute native/build.py), `script_sha256`, `inputs_sha256`, and `args`.
`args` is an array beginning with `validate` followed by the same flag/value
pairs used for the core build, including `--workspace`, `--source-cache`,
`--source-lock`, `--lock-sha256`, `--profile lfs-13.1-systemd`, and `--through ch08`.
Duplicate flags, other actions, `--help`, and unknown flags refuse. The validator
uses the native builder's fixed host PATH/locale, separate from dracut's target
pkg-config environment.

The external host-tool JSON has schema `tup.boot-tools.v1` and:

- `versions`: `{"dracut":"112","grub":"2.14"}`;
- `commands`: exactly `mksquashfs`, `dracut`, `lsinitrd`, `grub-mkrescue`,
  `grub-script-check`, and `xorriso`, each with absolute `path` and expected `sha256`;
- `path`: explicit absolute PATH directories supplying these tools and their
  reviewed host helpers;
- `support_trees`: objects with absolute `path` and expected `tree_hash()`;
- `grub_modules`: the separately hashed `x86_64-efi` directory;
- `grub_label_font`: absolute `path` and `sha256` for the DejaVu12 font shipped
  with the authenticated GRUB source; GRUB's EFI media-label renderer needs it
  even when optional fonts/themes/locales are disabled;
- `dracut_base`: the separately hashed host dracut framework directory;
- `provenance`: reference to retained source/package/build verification evidence.

Inspect without building, review the resulting input snapshot, then build with
that exact snapshot. Store all JSON input files outside the export:

```sh
python3 tup/boot/assemble.py inspect \
  --root "$TUP_EXPORT" --kernel-release 6.18.60-tup \
  --core-validator "$TUP_CORE_VALIDATOR" --layer-receipt "$TUP_BOOT_LAYER_RECEIPT" \
  --tools-lock "$TUP_HOST_TOOLS_LOCK" --tools-lock-sha256 "$TUP_VERIFIED_TOOLS_LOCK_SHA256" \
  > "$TUP_BOOT_INPUTS"

python3 tup/boot/assemble.py build \
  --root "$TUP_EXPORT" --kernel-release 6.18.60-tup \
  --core-validator "$TUP_CORE_VALIDATOR" --layer-receipt "$TUP_BOOT_LAYER_RECEIPT" \
  --tools-lock "$TUP_HOST_TOOLS_LOCK" --tools-lock-sha256 "$TUP_VERIFIED_TOOLS_LOCK_SHA256" \
  --expected-inputs "$TUP_BOOT_INPUTS" --output "$TUP_FRESH_ARTIFACT_DIRECTORY" \
  --jobs 4 --memory-mib 1024
```

No resume/overwrite switch exists. A mismatch needs diagnosis and a new reviewed
input snapshot; do not automatically replace the expected hash. Failed staging
directories are named `.tup-boot-*`, with `FAILED.txt` and available logs. A
durability failure renames any completion receipt to `ARTIFACT.uncertain.json`.
Only a zero-return build with `ARTIFACT.json` and no failure marker is a packaging
success. That still does not establish boot or release readiness.

## Dracut 112 under `--sysroot`: what was measured

These points come from running the pinned dracut 112 and lsinitrd on
2026-11-05, not from their documentation. The stand-in root was the builder's
own userland shaped like an export, with the real staged microcode and the
builder kernel's module tree. It is not a TUP root and nothing was booted.

- Dracut looks every source file up below `--sysroot` unless the text of its
  path starts with the sysroot (`dracut-install.c` lines 1398-1405; `inst_simple`,
  `dracut-functions.sh` lines 1149-1150). Given the host framework by its plain
  path, dracut printed `dracut-install: ERROR: installing` for each of its own
  scripts, failed to copy the `--include` directory, and still exited 0 with an
  initramfs that held no live hook. `assemble.py` now spells the host framework
  and every overlay file as `<root>/../...`, and passes overlay files one by
  one, because a directory given to `--include` is always copied from below
  the sysroot (`dracut.sh` lines 2915-2917).
- The module list used to be `bash base systemd systemd-initrd ...`. Dracut's
  `systemd-journald` module, which `systemd-initrd` needs, depends on
  `systemd-sysusers`, and that module requires the `systemd-sysusers` binary in
  the sysroot. LFS builds systemd with `-D sysusers=false`, and a sysroot
  without the binary made dracut stop with `Module 'systemd-initrd' cannot be
  installed`. The old list also never named `dracut-systemd`, the only module
  that installs the units which source dracut's hooks: built against the
  builder's userland it produced an initramfs with the hook files and nothing
  to run them. The list is now `bash base udev-rules kernel-modules rootfs-block
  dmsquash-live`. Dracut's own `init.sh` runs the same hook stages and needs
  neither. The packager refuses an initramfs that lists `systemd` without
  `dracut-systemd`, and one that lacks dracut's own live scripts.
- **Found on the first real root, which the stand-in could not show.** Dracut
  decides whether a kernel module exists with
  `modprobe -d "$drivers_dir/../../../" -S <release> --dry-run`
  (`dracut-functions.sh` lines 772-776), and `drivers_dir` is set only by
  `--kmoddir` (`dracut.sh` line 1148). Without that option the question goes
  to the builder's own `/lib/modules`, sysroot or not. The stand-in used the
  builder kernel's release, so it passed; the first packaging of a root with
  the TUP kernel (a rehearsal root) stopped with `Module 'dmsquash-live'
  depends on module 'overlayfs', which can't be installed`. `assemble.py` now
  passes `--kmoddir <root>/usr/lib/modules/<release>`. Rerun by hand on that
  root with the packager's exact command line plus this option, dracut exited
  0 with no output and an empty log, and the resulting initramfs passed every
  listing check: the eleven dracut modules, both hooks, the embedded digest
  file, the programs the hooks run, the udev daemon as systemd's link to
  `udevadm`, and an early cpio holding only the 128,644-byte AMD container.
  It has not been booted.
- With these changes the complete `assemble.py build` ran with the real tools
  on the stand-in: dracut printed no error, the ISO root holds `ventoy.dat`,
  both hooks and the digest are in the initramfs byte for byte, and the early
  cpio holds only `early_cpio` and an `AuthenticAMD.bin` whose SHA256 is the one
  in `../hardware/firmware-files.sha256`.

## Direct boot, diagnostics and Ventoy

GRUB searches a content-derived ISO volume label. The kernel command line uses
`root=live:LABEL=...`, never `/dev/sda`, `/dev/vda` or `/dev/sr0`. Dracut 112 uses a
512 MiB RAM OverlayFS upper directory; the compressed root stays on the media and
is not copied wholesale into RAM.

**Overlay size.** `rd.overlay=tmpfs:size=512M,nr_inodes=100000` is dracut 112's
spelling for a dedicated tmpfs under the upper directory
(`70overlayfs/prepare-overlayfs.sh` lines 24-44 and 82-97). The values reach
`mount -t tmpfs -o` unchanged, so `size=` takes `k`, `M`, `G` or a percentage of
RAM such as `size=25%`; a larger overlay is a change of `overlay_mib` in the
policy. Only `size`, `nr_blocks` and `nr_inodes` are accepted. Without the
`tmpfs:` form the upper directory would sit in `/run`, which dracut's init
mounts without a size (`init.sh` lines 66-77), so the kernel default of half of
RAM would be the only bound. `dmsquash-live-root.sh` reads the same value a
second time, as `<device>:<path>` of a persistent overlay (lines 149-161). It
looks for a device called `tmpfs`, finds no overlay there and waits for Enter
(lines 229-263): `read` under dracut's init, `systemd-ask-password --timeout=0`
under systemd. A headless boot would stop there. The command line therefore
adds `rd.live.overlay.nouserconfirmprompt`, the documented switch for exactly
that prompt (lines 29 and 227-228). This was measured by executing those lines
of the real script with command stubs. The stray `mount -o remount,rw tmpfs`
and failing `mount --bind` of lines 166-170 remain; they look harmless and are
unbooted. `rd.live.image`, `rd.live.dir`, `rd.live.squashimg`, `rd.live.ram=0`,
`rd.retry`, `rd.shell` and `rd.debug` are implemented under those names.

**Early microcode.** Without host-only mode dracut 112 concatenates every file
in `amd-ucode` and `intel-ucode` of its firmware directories into
`kernel/x86/microcode/AuthenticAMD.bin` and `GenuineIntel.bin` (`dracut.sh` lines
2969-3012), falls back to microcode archives in `<sysroot>/boot` (3013-3028),
and drops the feature with only a warning if it does not find
`CONFIG_MICROCODE=y` (2338-2357). Its default firmware path lies below the
sysroot but also follows the builder kernel's `firmware_class.path`; `--fwdir`
replaces it (1168-1172). The packager pins `--fwdir` to the export, requires
the single family 19h container before any tool runs, and afterwards unpacks
the leading cpio with `lsinitrd --unpackearly` into a fresh directory and
requires exactly `early_cpio` and an `AuthenticAMD.bin` with the staged SHA256.
That establishes what the image contains. Whether this CPU's model and stepping
take an update from it is a boot-time observation.

**Boot menu and consoles.** The last `console=` on the kernel command line
becomes `/dev/console`, where systemd writes its status lines and dracut opens
its emergency shell. The menu therefore has two entries with the same live
parameters. The default, for a desktop, ends with `console=tty0` and has no
shell tracing. The second, for a test VM that is read through its serial port,
ends with `console=ttyS0,115200n8` and adds `rd.debug` and
`systemd.log_target=console`. GRUB selects the second by itself when the
firmware's SMBIOS system manufacturer is `QEMU`
([`smbios`](https://www.gnu.org/software/grub/manual/grub/html_node/smbios.html)
command; the module is in the pinned GRUB 2.14 set); if the command is
unavailable the screen entry stays the default. GRUB writes to the serial port
but takes input only from the local console: with serial input enabled, noise
on an absent or unconnected UART could stop the three-second countdown of a
headless boot. The generated file passes the pinned `grub-script-check`. Which
entry a real QEMU and the real desktop take is a boot-time observation.

Serial output is 115200 8N1 on ttyS0. The first
test should use a disposable UEFI VM, a private copy of the firmware-variable
image, 4 GiB RAM, 4 vCPUs and no network. Record the exact ISO/firmware/runner hashes,
accelerator and device models. An external VM remains only a test tool.

Capture the serial stream to a host log. Dracut diagnostics are
`/run/initramfs/rdsosreport.txt` inside the failed guest; `rd.shell` is on in
both entries and `rd.debug` in the serial one. The live pre-pivot hook refuses missing/corrupt
SquashFS bytes. This verifies media integrity before switching root; it does not
authenticate the unsigned kernel/initramfs, and it runs after filesystem parsing.
It is not dm-verity, Secure Boot or protection from hostile replacement media.
Authenticated boot and stronger runtime payload integrity remain H19 work.

`ventoy.py` parses **captured** UEFI handoff data and validates its 512-byte
signature/checksum, disk marker, partition index, filesystem and ISO path. The
partition selector uses actual sysfs-style nodes and the parent's Ventoy marker,
so NVMe naming and reordered disks do not require guessing a suffix. It remains
the host-side reference; `ventoy-live.sh` is its early-userspace counterpart.

**Ventoy.** Started from an ISO file by Ventoy, GRUB sees a virtual CD but Linux
does not, so no block device carries the label. `ventoy-live.sh` is installed as
`/usr/lib/dracut/hooks/initqueue/settled/20-tup-ventoy-live.sh`. The initqueue
loop sources it every time udev has settled (`init.sh` lines 197-201;
`dracut-initqueue.sh` lines 42-46 under systemd). By then
`parse-dmsquash-live.sh` (cmdline 30, lines 21-23) has turned the label into
`/dev/disk/by-label/<label>` and `dmsquash-live-genrules.sh` (pre-udev 30,
lines 4-11) has written the udev rule that queues `dmsquash-live-root` when
that link appears. The hook only makes the link appear:

1. Without the variable
   `VentoyOsParam-77772020-2e77-6576-6e74-6f792e6e6574` the hook removes itself
   and does nothing else. Dracut's init does not mount efivarfs, so the hook
   looks through a private read-only mount and takes it away again.
2. The variable must pass the checks of `ventoy.py`: 516 efivarfs bytes,
   signature, checksum, nonzero disk GUID, partition 1-128, a known filesystem
   code, a nonzero size, and a NUL-terminated, zero-padded, valid UTF-8 absolute
   `.iso` path without empty, `.` or `..` components, backslashes or control
   characters. The shell also refuses a size of 2^48 bytes or more.
3. Candidate disks are those with a partition that udev recorded as
   `ID_FS_LABEL=VTOYEFI`, Ventoy's second partition. Other disks are judged from
   the udev database alone. Sector 0 of a candidate must hold the handoff's disk
   GUID at offset 384 and disk signature at offset 440. On that disk the
   partition with the recorded number, taken from sysfs and not from a device
   name, must have the recorded filesystem. Exactly one match is required.
4. That partition is mounted at `/run/initramfs/tup-ventoy/media` with
   `ro,nosuid,nodev,noexec`, plus `noload` for ext so that no journal is
   replayed and `utf8` for FAT. NTFS, XFS and UDF refuse: this kernel has no
   driver for them. The image must be a regular file of the recorded size,
   reached without a symbolic link. It is attached with `losetup -r`, and one
   `change` event is requested for that loop device.

The pattern is dracut's `70dmsquash-live/iso-scan.sh`. Four things differ: one
identified partition is mounted instead of every `/dev/disk/by-uuid/*`; the
loop device is read-only; one device gets an event instead of re-adding all of
them; and the mount point is not `/run/initramfs/isoscan`, which
`apply-live-updates.sh` (lines 18-22) would unmount ahead of TUP's digest hook
if `rd.live.ram` were set. Each refusal is one `tup-ventoy-live:` line through
dracut's `warn`, so it reaches the kernel log, the serial console and
`rdsosreport.txt`. It is also kept in `/run/initramfs/tup-ventoy/status` beside
a copy of the variable, and is repeated when the emergency shell opens. The
hook does not hash the ISO file; the pre-pivot digest hook still decides
whether the SquashFS is the packaged one.

**`ventoy.dat`.** The ISO root now has this file. Ventoy tests only that it
exists. Per its documentation and the 1.1.18 `grub.cfg` (`vt_check_compatible`,
`uefi_linux_menu_func`), Ventoy then treats the image as compatible: it does
not load its own hook cpio and does not replace the image's initrd, and only
presents the virtual disk and the handoff variable. The marker adds nothing
else. Ventoy's UEFI program sets the variable in its normal mode whatever the
marker says, without the non-volatile attribute, and does not set it in its
memdisk mode (`VentoyEfiMain` in its `Ventoy.c`). An image loaded to memory by
Ventoy therefore finds no handoff and no root; that mode is unsupported. The
marker is not evidence that this image boots through Ventoy: that has not
been run. Test a subdirectory/path containing spaces, reordered devices,
duplicate markers, missing media and corruption on disposable virtual media
before preparing the actual USB; the fixtures cover these cases only with
stubbed commands.

## Checks and remaining gates

```sh
python3 -m unittest discover -s tup/tests -p 'test_boot*.py' -v
bash -n tup/boot/verify-live.sh
sh -n tup/boot/ventoy-live.sh
```

The tests use synthetic input files and fake build-tool results. Linux runs
exercise real file/directory fsync, xattrs and metadata inventories; Windows
fixtures use a test-only durability adapter and skip Linux xattr/shell cases. They
test refusal/orchestration, not real SquashFS, initramfs or ISO compatibility.
`test_boot_ventoy_live.py` runs the hook's real shell code under bash and the
builder's `sh`: its parser against `ventoy.py` on synthetic handoffs, and the
whole hook, sourced the way the initqueue sources it, over a fake sysfs with
stubs for `mount`, `losetup` and `udevadm`. No device is opened.

Still required: build the target dependency layer; run the kernel
fragment through the actual 6.18.60 build; finish export/layer receipt integration;
repeat the dracut 112 run against the real TUP export, whose libraries, udev
rules and util-linux differ from the stand-in's; inspect/boot the
exact ISO; inject missing-driver/media failures; prove serial and private remote
access; boot the exact ISO through the pinned Ventoy on disposable media and
record what the hook did; implement/install on disposable
GPT/ESP images; and complete hardware and USB gates. Installed-root initramfs,
production boot authentication, the CPU's boot-time microcode revision, other
firmware, GPU and USB Wi-Fi remain open.

Primary sources consulted before implementation: [LFS kernel](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/kernel.html),
[LFS EFI GRUB](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/grub.html),
[BLFS initramfs](https://www.linuxfromscratch.org/blfs/view/stable-systemd/postlfs/initramfs.html),
[BLFS LVM2](https://www.linuxfromscratch.org/blfs/view/stable-systemd/postlfs/lvm2.html),
[systemd kernel requirements](https://raw.githubusercontent.com/systemd/systemd/v261/README),
[x86 kernel boot header](https://docs.kernel.org/arch/x86/boot.html),
[dracut 112](https://github.com/dracut-ng/dracut/releases/tag/112),
[dracut sysroot/configuration](https://dracut-ng.github.io/dracut/man/dracut.8.html),
[dracut 112 live module](https://raw.githubusercontent.com/dracut-ng/dracut/112/modules.d/70dmsquash-live/module-setup.sh),
[dracut 112 live command line](https://raw.githubusercontent.com/dracut-ng/dracut/112/man/dracut.cmdline.7.adoc),
[dracut 112 iso-scan](https://raw.githubusercontent.com/dracut-ng/dracut/112/modules.d/70dmsquash-live/iso-scan.sh),
[dracut 112 live root](https://raw.githubusercontent.com/dracut-ng/dracut/112/modules.d/70dmsquash-live/dmsquash-live-root.sh),
[dracut 112 init](https://raw.githubusercontent.com/dracut-ng/dracut/112/modules.d/80base/init.sh),
[dracut 112 main script](https://raw.githubusercontent.com/dracut-ng/dracut/112/dracut.sh),
[dracut 112 installer](https://raw.githubusercontent.com/dracut-ng/dracut/112/src/install/dracut-install.c),
[dracut 112 lsinitrd](https://raw.githubusercontent.com/dracut-ng/dracut/112/lsinitrd.sh),
[systemd 261 storage rules](https://raw.githubusercontent.com/systemd/systemd/v261/rules.d/60-persistent-storage.rules.in),
[Ventoy 1.1.18 UEFI program](https://raw.githubusercontent.com/ventoy/Ventoy/v1.1.18/EDK2/edk2_mod/edk2-edk2-stable201911/MdeModulePkg/Application/Ventoy/Ventoy.c),
[kernel microcode loading](https://docs.kernel.org/arch/x86/microcode.html),
[GRUB ISO implementation](https://raw.githubusercontent.com/rhboot/grub2/master/util/grub-mkrescue.c),
[SquashFS installation](https://raw.githubusercontent.com/plougher/squashfs-tools/4.7.5/Documentation/4.7.5/INSTALL),
[Ventoy record](https://www.ventoy.net/en/doc_compatible_format.html),
[EFI handoff](https://www.ventoy.net/en/doc_compatible_pass.html),
[ISO mounting](https://www.ventoy.net/en/doc_compatible_mount.html), and
[marker semantics](https://www.ventoy.net/en/doc_compatible_mark.html).
