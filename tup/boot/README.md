# Native UEFI test artifacts

This layer packages an explicitly supplied, offline x86_64 TUP export into a
**direct-UEFI test ISO**. Its executable entrypoint is `assemble.py`. It has not
built or booted a real TUP image yet. The installed system, installer, Ventoy
runtime integration, networking and hardware qualification remain separate gates.

The pipeline is:

1. Recheck pinned host tools, the exported root inventory, kernel header/config,
   matching module tree and the boot-layer receipt.
2. Run native `validate --through ch08 --profile lfs-13.1-systemd` against the
   original core workspace. Require a newly rewritten, matching
   `state/CORE-COMPLETION.json`; an old marker or zero exit alone is insufficient.
3. Package the export with `mksquashfs`, using the stated CPU/memory budget.
4. Run host dracut 112 with an explicit TUP `--sysroot`, host framework path,
   clean configuration/environment, and no host-only root configuration.
5. Embed the SquashFS digest and its pre-pivot verification hook. Inspect the
   resulting initramfs for both the hook/digest and required live modules.
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
records false boot/Ventoy claims. It preserves the core's source purpose,
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

## Direct boot, diagnostics and Ventoy

GRUB searches a content-derived ISO volume label. The kernel command line uses
`root=live:LABEL=...`, never `/dev/sda`, `/dev/vda` or `/dev/sr0`. Dracut 112 uses a
512 MiB RAM OverlayFS upper directory; the compressed root stays on the media and
is not copied wholesale into RAM. Serial output is 115200 8N1 on ttyS0. The first
test should use a disposable UEFI VM, a private copy of the firmware-variable
image, 4 GiB RAM, 4 vCPUs and no network. Record the exact ISO/firmware/runner hashes,
accelerator and device models. An external VM remains only a test tool.

Capture the serial stream to a host log. Dracut diagnostics are
`/run/initramfs/rdsosreport.txt` inside the failed guest; `rd.shell rd.debug` is
enabled for this test artifact. The live pre-pivot hook refuses missing/corrupt
SquashFS bytes. This verifies media integrity before switching root; it does not
authenticate the unsigned kernel/initramfs, and it runs after filesystem parsing.
It is not dm-verity, Secure Boot or protection from hostile replacement media.
Authenticated boot and stronger runtime payload integrity remain H19 work.

`ventoy.py` parses **captured** UEFI handoff data and validates its 512-byte
signature/checksum, disk marker, partition index, filesystem and ISO path. The
partition selector uses actual sysfs-style nodes and the parent's Ventoy marker,
so NVMe naming and reordered disks do not require guessing a suffix. It is a
host-side tested interface; no early-userspace parser/enumerator/mount adapter is
installed yet. This ISO contains no `ventoy.dat` and makes no compatibility claim.
The remaining adapter must find the selected USB filesystem, mount it read-only,
validate the selected ISO size/digest and loop-mount it, or use a reviewed Ventoy
device-mapper mapping. Test a subdirectory/path containing spaces, reordered
devices, duplicate markers, missing media and corruption using disposable virtual
media before adding a compatibility marker or preparing the actual USB.

## Checks and remaining gates

```sh
python3 -m unittest discover -s tup/tests -p 'test_boot*.py' -v
bash -n tup/boot/verify-live.sh
```

The tests use synthetic input files and fake build-tool results. Linux runs
exercise real file/directory fsync, xattrs and metadata inventories; Windows
fixtures use a test-only durability adapter and skip Linux xattr/shell cases. They
test refusal/orchestration, not real SquashFS, initramfs or ISO compatibility.

Still required: build the target dependency layer; run the kernel
fragment through the actual 6.18.60 build; finish export/layer receipt integration;
prove dracut 112's host/sysroot split with the real TUP libraries; inspect/boot the
exact ISO; inject missing-driver/media failures; prove serial and private remote
access; implement/test Ventoy runtime discovery; implement/install on disposable
GPT/ESP images; and complete hardware and USB gates. Installed-root initramfs,
production boot authentication, microcode/firmware, GPU and USB Wi-Fi remain open.

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
[GRUB ISO implementation](https://raw.githubusercontent.com/rhboot/grub2/master/util/grub-mkrescue.c),
[SquashFS installation](https://raw.githubusercontent.com/plougher/squashfs-tools/4.7.5/Documentation/4.7.5/INSTALL),
[Ventoy record](https://www.ventoy.net/en/doc_compatible_format.html),
[EFI handoff](https://www.ventoy.net/en/doc_compatible_pass.html),
[ISO mounting](https://www.ventoy.net/en/doc_compatible_mount.html), and
[marker semantics](https://www.ventoy.net/en/doc_compatible_mark.html).
